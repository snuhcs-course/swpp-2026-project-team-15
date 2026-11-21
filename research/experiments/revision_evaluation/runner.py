# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Sequential fresh/resumed research runs; CLI wiring remains separate."""

import time
from collections.abc import Callable
from datetime import UTC, datetime
from functools import wraps
from pathlib import Path

import httpx
from app.dishes.errors import DishLLMError
from app.dishes.roles import DishCatalog, RecipeBook

from .budgeting import BudgetedRunStore, BudgetExceeded, BudgetState, read_run_budget
from .checkpointing import AttemptCheckpointer, CheckpointReviser
from .compatibility import _digest, compatibility_fingerprint, validate_resume
from .contract import (
    OBSERVATION_SCHEMA,
    CodeIdentity,
    InputIdentities,
    Observation,
    ObservationInput,
    RunMetadata,
    RunSummary,
    validate_plan_unit_observations,
)
from .evaluation import evaluate_observation
from .live import LiveSettings, make_live_model, require_live_key
from .outcomes import persist_terminal
from .persistence import PersistenceError, _case_directory, _redact, _require_safe
from .planning import ExecutionPlan, publish_plan
from .staples import StaplesSnapshot
from .summary import summarize_run
from .telemetry import RevisionTiming, aggregate_telemetry, attempt_telemetry


def _now() -> str:
    """Use explicit UTC for persisted timestamps, independent of the host timezone."""
    return datetime.now(UTC).isoformat()


def _safe_run_errors(function):
    """Suppress credential-bearing exception text without reclassifying ordinary stops."""

    @wraps(function)
    def guarded(*args, **kwargs):
        key = require_live_key(kwargs.get("allow_live_api", False))
        try:
            return function(*args, **kwargs)
        except BaseException as error:
            if _redact(str(error), (key,)) != str(error):
                # Preserve callers' existing exception-type handling when its
                # constructor accepts safe text; never reuse private args/cause.
                try:
                    safe = type(error)("evaluation execution failed")
                    if _redact(str(safe), (key,)) != str(safe):
                        safe = PersistenceError("evaluation execution failed")
                except Exception:  # noqa: BLE001 - custom exception constructors may require other args
                    safe = PersistenceError("evaluation execution failed")
                raise safe from None
            raise

    return guarded


class _EvaluatedStore(BudgetedRunStore):
    """Attach pure findings before immutability, inside measured checkpoint storage.

    The checkpointer still owns timing and aggregation. The evaluator receives a
    copy and cannot change production inputs, decoded results or check decisions.
    Terminal coverage must be present in the first completed write, not patched
    into an already immutable observation after finish().
    """

    def write_observation(self, observation: Observation) -> str:
        return super().write_observation(evaluate_observation(observation))


def _initial(
    run_id: str,
    case_id: str,
    repetition: int,
    value: ObservationInput,
    *,
    execution_attempt: int = 1,
) -> Observation:
    """Create a new numbered execution with no fabricated latency or model evidence."""
    return Observation(
        artifact_schema=OBSERVATION_SCHEMA,
        run_id=run_id,
        case_id=case_id,
        repetition=repetition,
        execution_attempt=execution_attempt,
        input=value.model_copy(deep=True),
        execution={
            "state": "running",
            "checkpoint_revision": 1,
            "checkpoint_stage": "attempt_created",
            "started_at": _now(),
            "finished_at": None,
            "terminal_outcome": None,
            "outcome_source": None,
            "final_service_response": None,
            "sanitized_error": None,
        },
        model_calls=[],
        checks=[],
        deterministic_evaluation={
            "answers": [],
            "deleted_ingredient_explanation": {
                "numerator": 0,
                "denominator": 0,
                "value": None,
            },
        },
        telemetry=attempt_telemetry([], timing=RevisionTiming()),
    )


def _reconcile(durable: BudgetState) -> tuple[RunMetadata, dict[str, Observation]]:
    """Rebuild progress in memory from evidence; reject conflicting declared selections."""
    metadata = durable.metadata.model_copy(deep=True)
    observations = {
        f"observations/{_case_directory(item.case_id)}__r{item.repetition:02d}/"
        f"attempt-{item.execution_attempt:03d}.json": item
        for item in durable.observations
    }
    declared = [ref for unit in metadata.plan for ref in unit.observation_refs]
    if len(declared) != len(set(declared)):
        raise ValueError("observation references must be unique")
    if not set(declared).issubset(observations):
        raise ValueError(
            "observation references do not match their execution identities"
        )
    for unit in metadata.plan:
        validate_plan_unit_observations(
            unit, [observations[ref] for ref in unit.observation_refs]
        )
        refs = [
            ref
            for ref, item in observations.items()
            if (item.case_id, item.repetition) == (unit.case_id, unit.repetition)
        ]
        refs.sort(key=lambda ref: observations[ref].execution_attempt)
        attempts = [observations[ref] for ref in refs]
        completed = [item for item in attempts if item.execution.state == "completed"]
        if (
            [item.execution_attempt for item in attempts]
            != list(range(1, len(attempts) + 1))
            or len(completed) > 1
            or (completed and completed[0] is not attempts[-1])
        ):
            raise ValueError(
                "execution attempts must be contiguous with one terminal selection"
            )
        unit.observation_refs = refs
        unit.state = (
            "completed" if completed else "incomplete" if attempts else "not_started"
        )
        unit.selected_completed_attempt = (
            completed[0].execution_attempt if completed else None
        )
        unit.cumulative_telemetry = (
            aggregate_telemetry([item.telemetry for item in attempts])
            if attempts
            else None
        )
    metadata.http_attempt_budget = durable.budget
    return metadata, observations


def _publish_progress(store: _EvaluatedStore, *, state: str) -> RunSummary:
    """Publish durable progress without fabricating outcomes or rewriting checkpoints.

    Summary publication precedes completed metadata so a summary-write failure
    cannot leave an immutable completed run with no authoritative summary.
    """
    metadata, observations = _reconcile(read_run_budget(store.root))
    metadata.updated_at = _now()
    metadata.state = state
    summary = summarize_run(metadata, observations, generated_at=metadata.updated_at)
    store.write_summary(summary)
    store.write_metadata(metadata)
    return summary


def _validate_inputs(
    plan: ExecutionPlan,
    hashes: dict[str, str],
    snapshot: StaplesSnapshot,
    catalog: DishCatalog,
    recipes: RecipeBook,
) -> None:
    """Bind actual plan contents to identities and unchanged production input policy."""
    if hashes != {
        case: _digest(value.model_dump()) for case, value in plan.inputs.items()
    }:
        raise ValueError("metadata input hashes do not match the frozen plan")
    for value in plan.inputs.values():
        recipe, dish = recipes.get(value.dish_id), catalog.get(value.dish_id)
        if (
            recipe is None
            or dish is None
            or snapshot.input_snapshot(recipe, dish.name, value.supplied_ingredients)
            != value
        ):
            raise ValueError("execution inputs no longer match the frozen plan")


@_safe_run_errors
def run_new(
    plan: ExecutionPlan,
    metadata: RunMetadata,
    *,
    parent: Path,
    snapshot: StaplesSnapshot,
    catalog: DishCatalog,
    recipes: RecipeBook,
    settings: LiveSettings,
    allow_live_api: bool,
    transport_factory: Callable[[], httpx.BaseTransport] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> RunSummary:
    """Execute a fresh explicit plan sequentially, never reopen an existing run.

    The caller supplies captured code/input identities and the fingerprint for
    the full plan, in otherwise unstarted metadata. Authorization applies equally
    to a supplied mock transport; this function is never called by dry-run CLI.
    Persisted model failures complete a repetition; operational/configuration
    failures and interruptions escape unchanged and stop every later repetition.
    """
    key = require_live_key(allow_live_api)
    seed = RunMetadata.model_validate(metadata.model_dump(by_alias=True))
    frozen = ExecutionPlan(
        tuple(unit.model_copy(deep=True) for unit in plan.units),
        {case: value.model_copy(deep=True) for case, value in plan.inputs.items()},
        tuple(plan.effective_assumed_staples),
    )
    if (
        not frozen.units
        or len({(unit.case_id, unit.repetition) for unit in frozen.units})
        != len(frozen.units)
        or any(
            unit.state != "not_started" or unit.observation_refs
            for unit in frozen.units
        )
        or set(frozen.inputs) != {unit.case_id for unit in frozen.units}
        or seed.plan
        or seed.state != "running"
        or seed.resume_history
        or seed.http_attempt_budget.consumed
        or seed.http_attempt_budget.maximum != settings.maximum
        or seed.model != settings.model_metadata()
        or seed.pricing != settings.pricing_metadata()
        or tuple(seed.effective_assumed_staples) != snapshot.names
        or frozen.effective_assumed_staples != snapshot.names
    ):
        raise ValueError("fresh-run configuration does not match the unstarted plan")
    full = seed.model_copy(deep=True)
    full.plan = list(frozen.units)
    if compatibility_fingerprint(full) != seed.compatibility_fingerprint:
        raise ValueError("fresh-run compatibility fingerprint does not match")
    # A self-consistent metadata fingerprint does not bind it to the actual
    # execution inputs. Compare the entire map to reject missing/extra cases too.
    _validate_inputs(frozen, seed.identities.input_sha256, snapshot, catalog, recipes)
    _require_safe(seed.model_dump(by_alias=True), (key,))
    _require_safe(
        {case: value.model_dump() for case, value in frozen.inputs.items()}, (key,)
    )
    _require_safe([unit.model_dump() for unit in frozen.units], (key,))
    store = _EvaluatedStore(
        parent, seed.run_id, maximum=settings.maximum, snapshot=snapshot, secrets=(key,)
    )
    publish_plan(frozen, store, seed)
    return _execute(
        frozen,
        store,
        catalog=catalog,
        recipes=recipes,
        settings=settings,
        allow_live_api=allow_live_api,
        transport_factory=transport_factory,
        clock=clock,
    )


@_safe_run_errors
def run_resume(
    root: Path,
    plan: ExecutionPlan,
    identities: InputIdentities,
    code_identity: CodeIdentity,
    *,
    snapshot: StaplesSnapshot,
    catalog: DishCatalog,
    recipes: RecipeBook,
    settings: LiveSettings,
    allow_live_api: bool,
    transport_factory: Callable[[], httpx.BaseTransport] | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> RunSummary:
    """Validate current captured identities read-only, then continue the same run in place.

    The caller supplies freshly captured code/template/fixture identities, just as
    for the existing compatibility checker. Actual plan input hashes are always
    recomputed here. No old attempt, including a running checkpoint left by a hard
    interruption, is rewritten or relabelled as completed/interrupted on resume.
    """
    key = require_live_key(allow_live_api)
    frozen = ExecutionPlan(
        tuple(unit.model_copy(deep=True) for unit in plan.units),
        {case: value.model_copy(deep=True) for case, value in plan.inputs.items()},
        tuple(plan.effective_assumed_staples),
    )
    if (
        not frozen.units
        or frozen.effective_assumed_staples != snapshot.names
        or len({(unit.case_id, unit.repetition) for unit in frozen.units})
        != len(frozen.units)
        or set(frozen.inputs) != {unit.case_id for unit in frozen.units}
    ):
        raise ValueError("resume plan does not match the input policy")
    _validate_inputs(frozen, identities.input_sha256, snapshot, catalog, recipes)
    durable = read_run_budget(root, maximum=settings.maximum)
    validate_resume(
        durable.metadata,
        frozen,
        identities,
        code_identity,
        model=settings.model_metadata(),
        pricing=settings.pricing_metadata(),
    )
    # Reconciliation must also be read-only on corrupt progress. Canonical names
    # match the store's existing path policy, so unknown/unindexed evidence cannot
    # be ignored while calculating new attempt identities or budget consumption.
    metadata, observations = _reconcile(durable)
    _require_safe(metadata.model_dump(by_alias=True), (key,))
    for item in observations.values():
        _require_safe(item.model_dump(by_alias=True), (key,))
    for ref, item in observations.items():
        path = root.resolve() / ref
        if not path.resolve().is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError("durable attempt path does not match its identity")
        if item.input != frozen.inputs[item.case_id]:
            raise ValueError("durable attempt input differs from the frozen plan")
    # Validate reconciled states/selections and cumulative totals before any write.
    summarize_run(metadata, observations, generated_at=_now())
    pending = [unit for unit in metadata.plan if unit.state != "completed"]
    if pending and durable.budget.remaining == 0:
        raise BudgetExceeded("HTTP-attempt budget exhausted")
    store = _EvaluatedStore.open_existing(
        root, snapshot=snapshot, maximum=settings.maximum, secrets=(key,)
    )
    history = {"resumed_at": _now()}
    if pending:
        unit = pending[0]
        history.update(
            case_id=unit.case_id,
            repetition=unit.repetition,
            from_execution_attempt=len(unit.observation_refs),
        )
    metadata.resume_history.append(history)
    metadata.state, metadata.updated_at = "running", _now()
    store.write_metadata(metadata)
    return _execute(
        frozen,
        store,
        catalog=catalog,
        recipes=recipes,
        settings=settings,
        allow_live_api=allow_live_api,
        transport_factory=transport_factory,
        clock=clock,
    )


def _execute(
    plan: ExecutionPlan,
    store: _EvaluatedStore,
    *,
    catalog: DishCatalog,
    recipes: RecipeBook,
    settings: LiveSettings,
    allow_live_api: bool,
    transport_factory: Callable[[], httpx.BaseTransport] | None,
    clock: Callable[[], float],
) -> RunSummary:
    """Share sequential execution and stop behavior across fresh and resumed runs."""
    try:
        for unit in plan.units:
            durable = read_run_budget(store.root)
            attempts = [
                item
                for item in durable.observations
                if (item.case_id, item.repetition) == (unit.case_id, unit.repetition)
            ]
            if any(item.execution.state == "completed" for item in attempts):
                continue
            value = plan.inputs[unit.case_id]
            checkpointer = AttemptCheckpointer(
                store,
                _initial(
                    store.run_id,
                    unit.case_id,
                    unit.repetition,
                    value,
                    execution_attempt=max(
                        (item.execution_attempt for item in attempts), default=0
                    )
                    + 1,
                ),
                clock=clock,
                prices=settings.prices,
            )
            # Publish the incomplete unit before any model construction/send.
            _publish_progress(store, state="running")
            model = make_live_model(
                settings,
                checkpointer,
                allow_live_api=allow_live_api,
                transport=transport_factory()
                if transport_factory is not None
                else None,
            )
            reviser = CheckpointReviser(
                catalog, store.snapshot.index, model, recipes, checkpointer=checkpointer
            )
            response = error = None
            try:
                with checkpointer.measure_revision():
                    response = reviser.revise(
                        value.dish_id, list(value.supplied_ingredients)
                    )
            except DishLLMError as failure:
                error = failure
            if persist_terminal(checkpointer, response=response, error=error) is None:
                raise RuntimeError("Revision did not produce a completed result")
            _publish_progress(store, state="running")
        return _publish_progress(store, state="completed")
    except BaseException:
        # Best effort only: a broken disk must not mask the original stop, invent
        # an outcome, or permit another billable action. Durable attempts survive
        # even when this metadata/summary refresh also fails.
        try:
            _publish_progress(store, state="interrupted")
        except Exception:  # noqa: BLE001, S110 - preserve the original stop without logging secrets
            pass
        raise
