# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Mock-provider tests for durable budgets, uncertainty and authorization boundaries."""

import httpx
import pytest
from experiments.revision_evaluation import live
from experiments.revision_evaluation.budgeting import (
    BudgetedRunStore,
    read_run_budget,
)
from experiments.revision_evaluation.checkpointing import AttemptCheckpointer
from experiments.revision_evaluation.contract import Observation, PlanUnit, RunMetadata
from experiments.revision_evaluation.generate_contract import fixture_metadata, fixture_observations
from experiments.revision_evaluation.live import (
    LiveSettings,
    make_live_model,
    require_live_key,
    resolve_live_settings,
)
from experiments.revision_evaluation.persistence import PersistenceError
from experiments.revision_evaluation.staples import StaplesSnapshot
from experiments.revision_evaluation.telemetry import TokenPrices, aggregate_telemetry
from experiments.revision_evaluation.transport import CheckpointError

from app.dishes.llm import DishLLM
from tests.dishes.test_dishes import STAPLES
from tests.experiments.revision_evaluation.test_checkpointing import initial_observation


@pytest.fixture(autouse=True)
def mock_only(monkeypatch):
    """Keep real retry logic but replace waits; forbid actual socket connections."""
    import socket

    def forbidden(*args, **kwargs):
        raise AssertionError("test attempted a real network request")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(
        live, "DishLLM", lambda *args, **kwargs: DishLLM(*args, **kwargs, retry_waits=(0, 0))
    )
    monkeypatch.setenv("OPENROUTER_API_KEY", "private-test-key")


def setup_run(tmp_path, maximum=2, *, prices=None):
    """Persist the original cap and policy before creating any active attempt."""
    snapshot = StaplesSnapshot(list(STAPLES))
    initial = initial_observation(snapshot.catalog())
    settings = LiveSettings("fixture/model", maximum, prices)
    store = BudgetedRunStore(
        tmp_path, initial.run_id, maximum=maximum, snapshot=snapshot, secrets=("private-test-key",)
    )
    metadata = RunMetadata.model_validate(fixture_metadata(fixture_observations()))
    metadata.run_id = initial.run_id
    metadata.state = "running"
    metadata.plan = [
        PlanUnit(
            case_id=initial.case_id,
            repetition=1,
            state="not_started",
            observation_refs=[],
            selected_completed_attempt=None,
            cumulative_telemetry=None,
        )
    ]
    metadata.effective_assumed_staples = list(snapshot.names)
    metadata.model = settings.model_metadata()
    metadata.pricing = settings.pricing_metadata()
    metadata.http_attempt_budget = metadata.http_attempt_budget.model_validate(
        {"maximum": maximum, "consumed": 0, "remaining": maximum}
    )
    store.write_metadata(metadata)
    return store, initial, settings, metadata


def response():
    """Return a billed successful answer without imposing recipe scoring policy."""
    return httpx.Response(
        200,
        json={
            "choices": [{"finish_reason": "stop", "message": {"content": "{}"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "cost": 0.01},
        },
    )


@pytest.mark.parametrize("maximum", [0, -1, True, 1.5, None])
def test_invalid_cap_is_rejected_before_run_creation(tmp_path, maximum):
    with pytest.raises(ValueError):
        BudgetedRunStore(tmp_path, "run", maximum=maximum)
    assert not list(tmp_path.iterdir())


def test_retry_is_stopped_before_send_or_over_budget_checkpoint(tmp_path):
    store, initial, settings, _ = setup_run(tmp_path, maximum=1)
    checkpointer = AttemptCheckpointer(store, initial)
    sends = []

    def handle(request):
        state = read_run_budget(store.root)
        assert state.budget.consumed == 1
        assert state.observations[0].model_calls[0].http_attempts[0].state == "request_prepared"
        sends.append(request)
        return httpx.Response(429, json={"error": "not persisted"})

    model = make_live_model(
        settings, checkpointer, allow_live_api=True, transport=httpx.MockTransport(handle)
    )
    with pytest.raises(CheckpointError):
        model.complete("system", "user", "revision", {})
    assert len(sends) == 1
    state = read_run_budget(store.root)
    assert state.budget.consumed == 1 and state.budget.remaining == 0
    assert len(state.observations[0].model_calls[0].http_attempts) == 1


def test_reask_and_later_calls_cannot_spend_after_cap(tmp_path):
    store, initial, settings, _ = setup_run(tmp_path, maximum=1)
    checkpointer = AttemptCheckpointer(store, initial)
    sends = []
    model = make_live_model(
        settings,
        checkpointer,
        allow_live_api=True,
        transport=httpx.MockTransport(lambda request: sends.append(request) or response()),
    )
    assert model.complete("system", "user", "initial", {}) == {}
    before = {path: path.read_bytes() for path in store.root.rglob("*.json")}
    with pytest.raises(CheckpointError):
        model.complete("system", "user", "reask", {})
    assert len(sends) == 1
    assert {path: path.read_bytes() for path in store.root.rglob("*.json")} == before


def interrupted_prepared(initial):
    """Keep an uncertain earlier execution under the same planned repetition."""
    raw = fixture_observations()["resumed__r03/attempt-001.json"]
    raw.update(run_id=initial.run_id, case_id=initial.case_id, repetition=initial.repetition)
    raw["input"] = initial.input.model_dump()
    return Observation.model_validate(raw)


def test_unindexed_interruption_consumes_budget_and_preserves_known_subtotals(tmp_path):
    store, initial, settings, _ = setup_run(tmp_path, maximum=2)
    prior = interrupted_prepared(initial)
    prior_ref = store.write_observation(prior)
    prior_bytes = (store.root / prior_ref).read_bytes()
    initial.execution_attempt = 2
    checkpointer = AttemptCheckpointer(store, initial)
    sends = []
    model = make_live_model(
        settings,
        checkpointer,
        allow_live_api=True,
        transport=httpx.MockTransport(lambda request: sends.append(request) or response()),
    )
    model.complete("system", "user", "initial", {})
    assert len(sends) == 1
    state = read_run_budget(store.root)
    # Metadata deliberately still says consumed=0 and has no observation refs.
    assert state.metadata.http_attempt_budget.consumed == 0
    assert state.budget.consumed == 2 and state.budget.remaining == 0
    totals = aggregate_telemetry([value.telemetry for value in state.observations])
    assert totals.tokens.input_tokens.value is None
    assert totals.tokens.input_tokens.confirmed_subtotal == 10
    assert totals.cost_usd.provenance == "missing"
    assert totals.cost_usd.confirmed_subtotal == 0.01
    assert (store.root / prior_ref).read_bytes() == prior_bytes
    with pytest.raises(PersistenceError):
        read_run_budget(store.root, maximum=3)
    assert (store.root / prior_ref).read_bytes() == prior_bytes


def test_metadata_cannot_reset_budget_or_replace_original_cap(tmp_path):
    store, initial, _, metadata = setup_run(tmp_path, maximum=1)
    store.write_observation(interrupted_prepared(initial))
    before = (store.root / "metadata.json").read_bytes()
    with pytest.raises(ValueError, match="every durable"):
        store.write_metadata(metadata)
    metadata.http_attempt_budget.maximum = 2
    metadata.http_attempt_budget.remaining = 2
    with pytest.raises(ValueError, match="cannot change"):
        store.write_metadata(metadata)
    assert (store.root / "metadata.json").read_bytes() == before


def test_pre_request_storage_failure_spends_no_budget_and_sends_nothing(tmp_path, monkeypatch):
    store, initial, settings, _ = setup_run(tmp_path, maximum=1)
    checkpointer = AttemptCheckpointer(store, initial)
    sends = []
    model = make_live_model(
        settings,
        checkpointer,
        allow_live_api=True,
        transport=httpx.MockTransport(lambda request: sends.append(request) or response()),
    )

    def fail(*args):
        raise OSError("private-test-key")

    monkeypatch.setattr(store, "_write", fail)
    with pytest.raises(CheckpointError):
        model.complete("system", "user", "initial", {})
    assert not sends
    assert read_run_budget(store.root).budget.consumed == 0


def test_authorization_precedes_credential_reads(monkeypatch):
    class NoRead:
        def get(self, key, default=None):
            raise AssertionError("must not inspect credentials without opt-in")

    with monkeypatch.context() as scoped:
        scoped.setattr(live.os, "environ", NoRead())
        with pytest.raises(ValueError, match="opt-in"):
            require_live_key(False)
    monkeypatch.delenv("OPENROUTER_API_KEY")
    with pytest.raises(ValueError, match="configured API key"):
        require_live_key(True)


def test_failed_response_write_retains_uncertain_budget_and_stops_retry(tmp_path, monkeypatch):
    store, initial, settings, _ = setup_run(tmp_path, maximum=2)
    checkpointer = AttemptCheckpointer(store, initial)
    write = store._write
    sends = []

    def save(relative, value):
        if (
            relative.startswith("observations/")
            and value["execution"]["checkpoint_stage"] == "response_received"
        ):
            raise OSError("private-test-key")
        return write(relative, value)

    monkeypatch.setattr(store, "_write", save)
    model = make_live_model(
        settings,
        checkpointer,
        allow_live_api=True,
        transport=httpx.MockTransport(lambda request: sends.append(request) or httpx.Response(429)),
    )
    with pytest.raises(CheckpointError):
        model.complete("system", "user", "initial", {})
    state = read_run_budget(store.root)
    assert len(sends) == 1 and state.budget.consumed == 1
    recorded = state.observations[0].model_calls[0].http_attempts[0]
    assert recorded.state == "request_prepared" and recorded.delivery == "unknown"


def test_budget_scan_time_is_excluded_from_production_clock(tmp_path, monkeypatch):
    from experiments.revision_evaluation import budgeting

    store, initial, settings, _ = setup_run(tmp_path, maximum=2)
    now = [0.0]
    scan = budgeting._observations

    def slow_scan(*args):
        now[0] += 30
        return scan(*args)

    monkeypatch.setattr(budgeting, "_observations", slow_scan)
    checkpointer = AttemptCheckpointer(store, initial, clock=lambda: now[0])
    model = make_live_model(
        settings,
        checkpointer,
        allow_live_api=True,
        transport=httpx.MockTransport(lambda request: response()),
    )
    # Factory validation is setup, outside the measured Revision window.
    started = checkpointer.policy_time()
    with checkpointer.measure_revision():
        model.complete("system", "user", "initial", {})
    assert checkpointer.policy_time() == started
    assert checkpointer.checkpoint_persistence_s >= 60


@pytest.mark.parametrize(
    "changes",
    [
        {"model_id": ""},
        {"maximum": 0},
        {"input_price": -1, "output_price": 0},
        {"input_price": float("nan"), "output_price": 0},
        {"input_price": 1},
    ],
)
def test_invalid_live_settings_are_not_repaired(changes):
    with pytest.raises(ValueError):
        resolve_live_settings(**{"maximum": 1, **changes})


def test_each_model_factory_uses_a_fresh_recorder_and_persisted_prices(tmp_path):
    prices = TokenPrices(0.1, 0.4)
    store, initial, settings, _ = setup_run(tmp_path, prices=prices)
    checkpointer = AttemptCheckpointer(store, initial, prices=prices)
    first = make_live_model(
        settings,
        checkpointer,
        allow_live_api=True,
        transport=httpx.MockTransport(lambda request: response()),
    )
    second = make_live_model(
        settings,
        checkpointer,
        allow_live_api=True,
        transport=httpx.MockTransport(lambda request: response()),
    )
    assert first is not second and first.calls is not second.calls
    assert first.calls == second.calls == []
    with pytest.raises(ValueError, match="persisted run"):
        make_live_model(
            LiveSettings("other/model", 2, prices),
            checkpointer,
            allow_live_api=True,
            transport=httpx.MockTransport(lambda request: response()),
        )
