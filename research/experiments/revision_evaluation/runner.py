# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Sequential fresh-run assembly; CLI wiring and compatible store reopening are separate."""

import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import httpx
from app.dishes.errors import DishLLMError
from app.dishes.roles import DishCatalog, RecipeBook

from .budgeting import BudgetedRunStore, read_run_budget
from .checkpointing import AttemptCheckpointer, CheckpointReviser
from .compatibility import _digest, compatibility_fingerprint
from .contract import (
    OBSERVATION_SCHEMA,
    Observation,
    ObservationInput,
    RunMetadata,
    RunSummary,
)
from .evaluation import evaluate_observation
from .live import LiveSettings, make_live_model, require_live_key
from .outcomes import persist_terminal
from .persistence import _case_directory
from .planning import ExecutionPlan, publish_plan
from .staples import StaplesSnapshot
from .summary import summarize_run
from .telemetry import RevisionTiming, aggregate_telemetry, attempt_telemetry


def _now() -> str:
    """Use explicit UTC for persisted timestamps, independent of the host timezone."""
    return datetime.now(UTC).isoformat()


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
    run_id: str, case_id: str, repetition: int, value: ObservationInput
) -> Observation:
    """Create an empty first execution with no fabricated latency or model evidence."""
    return Observation(
        artifact_schema=OBSERVATION_SCHEMA,
        run_id=run_id,
        case_id=case_id,
        repetition=repetition,
        execution_attempt=1,
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


def _publish_progress(store: _EvaluatedStore, *, state: str) -> RunSummary:
    """Derive the index and summary from durable checkpoints, including a lagging intent.

    A stop never fabricates a terminal observation or rewrites the last checkpoint.
    Summary publication precedes completed metadata so a summary-write failure
    cannot leave an immutable completed run with no authoritative summary.
    """
    durable = read_run_budget(store.root)
    metadata = durable.metadata.model_copy(deep=True)
    observations = {
        f"observations/{_case_directory(item.case_id)}__r{item.repetition:02d}/"
        f"attempt-{item.execution_attempt:03d}.json": item
        for item in durable.observations
    }
    for unit in metadata.plan:
        refs = [
            ref
            for ref, item in observations.items()
            if (item.case_id, item.repetition) == (unit.case_id, unit.repetition)
        ]
        refs.sort(key=lambda ref: observations[ref].execution_attempt)
        attempts = [observations[ref] for ref in refs]
        completed = [item for item in attempts if item.execution.state == "completed"]
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
    metadata.updated_at = _now()
    metadata.state = state
    summary = summarize_run(metadata, observations, generated_at=metadata.updated_at)
    store._write("summary.json", summary.model_dump(by_alias=True))
    store.write_metadata(metadata)
    return summary


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
    if seed.identities.input_sha256 != {
        case_id: _digest(value.model_dump()) for case_id, value in frozen.inputs.items()
    }:
        raise ValueError("metadata input hashes do not match the frozen plan")
    for value in frozen.inputs.values():
        recipe = recipes.get(value.dish_id)
        dish = catalog.get(value.dish_id)
        if (
            recipe is None
            or dish is None
            or snapshot.input_snapshot(recipe, dish.name, value.supplied_ingredients)
            != value
        ):
            raise ValueError("execution inputs no longer match the frozen plan")
    store = _EvaluatedStore(
        parent, seed.run_id, maximum=settings.maximum, snapshot=snapshot, secrets=(key,)
    )
    publish_plan(frozen, store, seed)
    try:
        for unit in frozen.units:
            value = frozen.inputs[unit.case_id]
            checkpointer = AttemptCheckpointer(
                store,
                _initial(seed.run_id, unit.case_id, unit.repetition, value),
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
                catalog, snapshot.index, model, recipes, checkpointer=checkpointer
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
