# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Offline accounting tests for partial usage, resume totals and isolated timing."""

import json
from copy import deepcopy

import httpx
import pytest
from app.dishes.catalog import Catalog
from app.dishes.errors import DishLLMError
from app.dishes.llm import DishLLM
from app.dishes.recipes import RecipeStore
from app.dishes.schemas import SourceRecipe
from experiments.revision_evaluation import telemetry as telemetry_module
from experiments.revision_evaluation.checkpointing import (
    AttemptCheckpointer,
    CheckpointModelCallRecorder,
    CheckpointReviser,
    CheckpointTransport,
)
from experiments.revision_evaluation.contract import Cost, Observation, Telemetry
from experiments.revision_evaluation.generate_contract import fixture_metadata, fixture_observations
from experiments.revision_evaluation.outcomes import persist_terminal
from experiments.revision_evaluation.persistence import RunStore
from experiments.revision_evaluation.telemetry import (
    RevisionTiming,
    TokenPrices,
    aggregate_telemetry,
    attempt_telemetry,
    repetition_telemetry,
)
from experiments.revision_evaluation.transport import CheckpointError
from tests.dishes.test_dishes import STAPLES
from tests.dishes.test_revision import GOOD, RECIPE
from tests.experiments.revision_evaluation.test_checkpointing import initial_observation


def observation(case="resumed__r03/attempt-002.json"):
    """Return independent contract evidence for an accounting scenario."""
    return Observation.model_validate(fixture_observations()[case])


def test_zero_call_values_are_inapplicable_not_missing_or_zero():
    totals = attempt_telemetry([], timing=RevisionTiming(0, 0))
    assert totals.http_attempts == totals.logical_calls == 0
    assert totals.cost_usd.provenance == "not_applicable"
    assert totals.tokens.input_tokens.applicability == "not_applicable"
    assert totals.provider_round_trip_s.applicability == "not_applicable"
    assert totals.revision_s.value == totals.non_http_remainder_s.value == 0


def test_all_calls_http_retries_and_received_usage_are_counted():
    value = observation("revised-after-reask-429__r01/attempt-001.json")
    totals = attempt_telemetry(value.model_calls, timing=RevisionTiming(5, 1))
    assert (totals.logical_calls, totals.reasks, totals.http_attempts) == (2, 1, 3)
    assert totals.http_429_responses == totals.http_429_retries == 1
    assert totals.provider_round_trip_s.value == 0.75
    assert totals.revision_s.value == 4 and totals.non_http_remainder_s.value == 3.25
    assert totals.tokens.input_tokens.value is None
    assert totals.tokens.input_tokens.confirmed_subtotal == 20
    assert totals.cost_usd.provenance == "missing"
    assert totals.cost_usd.confirmed_subtotal == 0.0002
    # A terminal 429 is a response, not a retry that never happened.
    first = value.model_calls[0].model_copy(deep=True)
    first.http_attempts = first.http_attempts[:1]
    totals = attempt_telemetry([first])
    assert totals.http_429_responses == 1 and totals.http_429_retries == 0


def test_unknown_prepared_request_cannot_be_estimated_even_with_prices():
    calls = observation("resumed__r03/attempt-001.json").model_calls
    totals = attempt_telemetry(calls, prices=TokenPrices(1, 2))
    assert totals.http_attempts == 1
    assert totals.cost_usd.provenance == "missing" and totals.cost_usd.value is None
    assert totals.tokens.input_tokens.applicability == "unavailable"
    assert totals.provider_round_trip_s.applicability == "unavailable"
    assert totals.non_http_remainder_s.applicability == "unavailable"


@pytest.mark.parametrize(
    "input_tokens,output_tokens,expected", [(10, 20, 0.00005), (0, 0, 0), (None, 20, None)]
)
def test_estimates_require_complete_input_output_usage_and_preserve_price_inputs(
    input_tokens, output_tokens, expected
):
    value = observation()
    http = value.model_calls[0].http_attempts[0]
    http.cost_usd = Cost(
        applicability="unavailable",
        value=None,
        confirmed_subtotal=0,
        provenance="missing",
        price_inputs=None,
    )
    http.usage.input_tokens, http.usage.output_tokens = input_tokens, output_tokens
    before = value.model_dump()
    totals = attempt_telemetry(value.model_calls, prices=TokenPrices(1, 2))
    assert totals.cost_usd.value == expected
    assert totals.cost_usd.provenance == ("estimated" if expected is not None else "missing")
    if expected is not None:
        assert totals.cost_usd.price_inputs == {
            "input_per_million_usd": 1,
            "output_per_million_usd": 2,
        }
    assert value.model_dump() == before


def test_provider_cost_wins_and_each_token_category_remains_independent():
    value = observation()
    http = value.model_calls[0].http_attempts[0]
    http.usage.reasoning_tokens = None
    totals = attempt_telemetry(value.model_calls, prices=TokenPrices(100, 200))
    assert totals.cost_usd.provenance == "measured" and totals.cost_usd.value == 0.0001
    assert totals.tokens.input_tokens.value == 10
    assert totals.tokens.reasoning_tokens.value is None
    assert totals.tokens.cached_tokens.value == 0


def test_known_partial_billing_is_not_overwritten_by_a_smaller_estimate():
    value = observation()
    value.model_calls[0].http_attempts[0].cost_usd = Cost(
        applicability="unavailable",
        value=None,
        confirmed_subtotal=0.5,
        provenance="missing",
        price_inputs=None,
    )
    totals = attempt_telemetry(value.model_calls, prices=TokenPrices(1, 2))
    assert totals.cost_usd.provenance == "missing"
    assert totals.cost_usd.confirmed_subtotal == 0.5


def test_cumulative_resume_includes_incomplete_superseded_attempt_and_preserves_subtotals():
    interrupted, completed = observation("resumed__r03/attempt-001.json"), observation()
    interrupted.telemetry = attempt_telemetry(interrupted.model_calls)
    completed.telemetry = attempt_telemetry(completed.model_calls, timing=RevisionTiming(1, 0.2))
    before = deepcopy([interrupted.model_dump(), completed.model_dump()])
    totals = repetition_telemetry([interrupted, completed])
    assert totals.logical_calls == totals.http_attempts == 2
    assert totals.cost_usd.value is None and totals.cost_usd.confirmed_subtotal == 0.0001
    assert totals.tokens.input_tokens.value is None
    assert totals.tokens.input_tokens.confirmed_subtotal == 10
    assert totals.revision_s.applicability == "unavailable"
    assert [interrupted.model_dump(), completed.model_dump()] == before
    with pytest.raises(ValueError, match="unique execution attempts"):
        repetition_telemetry([completed, completed])
    interrupted.case_id = "different-case"
    with pytest.raises(ValueError, match="one repetition"):
        repetition_telemetry([interrupted, completed])


def test_interrupted_attempts_retain_usage_incurred_before_an_inflight_request():
    interrupted = observation("revised-after-reask-429__r01/attempt-001.json")
    completed = observation()
    interrupted.case_id, interrupted.repetition = completed.case_id, completed.repetition
    interrupted.execution.state = "interrupted"
    interrupted.execution.terminal_outcome = interrupted.execution.outcome_source = None
    prepared = observation("resumed__r03/attempt-001.json").model_calls[0].http_attempts[0]
    prepared.index = 2
    interrupted.model_calls[-1].http_attempts.append(prepared)
    interrupted.telemetry = attempt_telemetry(interrupted.model_calls)
    completed.telemetry = attempt_telemetry(completed.model_calls)
    totals = repetition_telemetry([interrupted, completed])
    assert totals.http_attempts == 5
    assert totals.tokens.input_tokens.value is None
    assert totals.tokens.input_tokens.confirmed_subtotal == 30
    assert totals.cost_usd.value is None
    assert totals.cost_usd.confirmed_subtotal == pytest.approx(0.0003)


def test_empty_aggregate_and_zero_provider_cost_are_distinct():
    empty = aggregate_telemetry([])
    assert empty.cost_usd.provenance == "not_applicable"
    assert empty.tokens.output_tokens.applicability == "not_applicable"
    value = observation()
    cost = value.model_calls[0].http_attempts[0].cost_usd
    cost.value = cost.confirmed_subtotal = 0
    zero = attempt_telemetry(value.model_calls, prices=TokenPrices(1, 2))
    assert zero.cost_usd.provenance == "measured"
    assert zero.cost_usd.value == 0 and zero.cost_usd.price_inputs is None


def test_aggregate_matches_independent_fixture_metadata():
    observations = fixture_observations()
    for unit in fixture_metadata(observations)["plan"]:
        values = [
            Telemetry.model_validate(
                observations[reference.removeprefix("observations/")]["telemetry"]
            )
            for reference in unit["observation_refs"]
        ]
        expected = Telemetry.model_validate(unit["cumulative_telemetry"])
        actual = aggregate_telemetry(values)
        for name in telemetry_module.COUNT_FIELDS:
            assert getattr(actual, name) == getattr(expected, name)
        assert actual.tokens == expected.tokens
        assert actual.cost_usd.provenance == expected.cost_usd.provenance
        assert actual.cost_usd.confirmed_subtotal == pytest.approx(
            expected.cost_usd.confirmed_subtotal
        )
        assert actual.cost_usd.value == pytest.approx(expected.cost_usd.value)
        for name in telemetry_module.TIME_FIELDS:
            measured, frozen = getattr(actual, name), getattr(expected, name)
            assert measured.applicability == frozen.applicability
            assert measured.value == pytest.approx(frozen.value)


def test_aggregation_ignores_na_but_not_missing_and_retains_estimated_provenance():
    measured = attempt_telemetry(observation().model_calls)
    calls = observation().model_calls
    calls[0].http_attempts[0].cost_usd = Cost(
        applicability="unavailable",
        value=None,
        confirmed_subtotal=0,
        provenance="missing",
        price_inputs=None,
    )
    estimate = attempt_telemetry(calls, prices=TokenPrices(1, 2))
    totals = aggregate_telemetry([attempt_telemetry([]), measured, estimate])
    assert totals.cost_usd.value == pytest.approx(0.00015)
    assert totals.cost_usd.provenance == "estimated"
    assert totals.tokens.input_tokens.value == 20
    missing = attempt_telemetry(observation("resumed__r03/attempt-001.json").model_calls)
    partial = aggregate_telemetry([totals, missing])
    assert partial.cost_usd.provenance == "missing"
    assert partial.cost_usd.confirmed_subtotal == pytest.approx(0.00015)
    other_prices = attempt_telemetry(calls, prices=TokenPrices(2, 3))
    with pytest.raises(ValueError, match="different estimate price inputs"):
        aggregate_telemetry([estimate, other_prices])


@pytest.mark.parametrize("price", [-1, float("nan"), float("inf"), True])
def test_invalid_prices_are_rejected_before_accounting(price):
    with pytest.raises(ValueError, match="token prices"):
        TokenPrices(price, 1)


def test_inconsistent_timing_is_not_silently_reported_as_processing():
    with pytest.raises(ValueError, match="cannot exceed"):
        RevisionTiming(1, 2)
    with pytest.raises(ValueError, match="provider duration exceeds"):
        attempt_telemetry(observation().model_calls, timing=RevisionTiming(0.1, 0))


@pytest.mark.parametrize("duration", [-1, float("nan"), float("inf")])
def test_nonfinite_or_negative_timings_are_rejected(duration):
    with pytest.raises(ValueError, match="timing"):
        RevisionTiming(duration, 0)


@pytest.mark.parametrize(
    "error", [DishLLMError("The model service could not be reached"), RuntimeError("interrupted")]
)
def test_timing_window_distinguishes_model_completion_from_operational_interruption(
    tmp_path, error
):
    now = [0.0]
    store = RunStore(tmp_path, "checkpoint-run")
    controller = AttemptCheckpointer(
        store, initial_observation(Catalog.load(staples=STAPLES)), clock=lambda: now[0]
    )
    with pytest.raises(type(error)) as caught:
        with controller.measure_revision():
            now[0] += 2
            raise error
    assert caught.value is error
    timing = controller._timing
    assert timing.observed_wall_s == (2 if isinstance(error, DishLLMError) else None)
    assert timing.checkpoint_persistence_s == 0
    # Timing alone never changes incomplete execution into an invented outcome.
    assert controller.observation.execution.terminal_outcome is None


def test_failed_telemetry_projection_is_operational_and_preserves_durable_snapshot(
    tmp_path, monkeypatch
):
    store = RunStore(tmp_path, "checkpoint-run")
    controller = AttemptCheckpointer(store, initial_observation(Catalog.load(staples=STAPLES)))
    path = store.root / controller.reference
    before = path.read_bytes()

    def fail(*args, **kwargs):
        raise ValueError("private-accounting-detail")

    monkeypatch.setattr(telemetry_module, "attempt_telemetry", fail)
    with pytest.raises(CheckpointError, match="^checkpoint persistence failed$"):
        controller.record_checks([])
    assert path.read_bytes() == before
    assert controller.observation.execution.checkpoint_revision == 1


@pytest.mark.parametrize("projection_delay", [0, 90])
def test_live_checkpoints_publish_complete_timing_without_checkpoint_delaying_reask(
    tmp_path, monkeypatch, projection_delay
):
    now, sends = [0.0], []
    projections = []
    project = telemetry_module.attempt_telemetry

    def slow_projection(*args, **kwargs):
        projections.append(True)
        now[0] += projection_delay
        return project(*args, **kwargs)

    monkeypatch.setattr(telemetry_module, "attempt_telemetry", slow_projection)
    store = RunStore(tmp_path, "checkpoint-run")
    write = store.write_observation

    def save(value):
        reference = write(value)
        now[0] += 90  # Persistence alone would exceed the production retry/re-ask budget.
        return reference

    store.write_observation = save

    def handle(request):
        sends.append(request)
        now[0] += 0.25
        answer = {**GOOD, "changes": []} if len(sends) == 1 else GOOD
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(answer)}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "cost": 0.01},
            },
        )

    catalog = Catalog.load(staples=STAPLES)
    controller = AttemptCheckpointer(store, initial_observation(catalog), clock=lambda: now[0])
    transport = CheckpointTransport(httpx.MockTransport(handle), checkpointer=controller)
    model = CheckpointModelCallRecorder(
        DishLLM("test-key", transport=transport, retry_waits=(), clock=controller.policy_time),
        checkpointer=controller,
    )
    recipes = RecipeStore({RECIPE["dish_id"]: SourceRecipe.model_validate(RECIPE)})
    reviser = CheckpointReviser(catalog, catalog, model, recipes, checkpointer=controller)
    with controller.measure_revision():
        response = reviser.revise(RECIPE["dish_id"], ["밥", "김치"])
    persist_terminal(controller, response=response)
    saved = Observation.model_validate_json(
        (store.root / controller.reference).read_text(encoding="utf-8")
    )
    assert len(sends) == 2 and saved.execution.terminal_outcome == "revised"
    assert saved.telemetry.revision_s.value == saved.telemetry.provider_round_trip_s.value == 0.5
    assert saved.telemetry.non_http_remainder_s.value == 0
    assert saved.telemetry.checkpoint_persistence_s.value == 10 * (90 + projection_delay)
    assert saved.telemetry.observed_wall_s.value == 10 * (90 + projection_delay) + 0.5
    assert saved.telemetry.tokens.input_tokens.value == 20
    assert saved.telemetry.cost_usd.value == 0.02
    # One aggregation per revision, and both adapters expose the same clock source.
    assert len(projections) == saved.execution.checkpoint_revision == 12
    assert transport.checkpoint_persistence_s == controller.checkpoint_persistence_s
    assert transport.policy_time() == controller.policy_time()
    with pytest.raises(ValueError, match="only be measured once"):
        with controller.measure_revision():
            pass
