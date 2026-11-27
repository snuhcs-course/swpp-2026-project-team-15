# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An.
"""Offline fresh-run integration with real production Revision and mock HTTP only."""

import hashlib
import json
import socket
from copy import deepcopy

import httpx
import pytest
from experiments.revision_evaluation import live, runner
from experiments.revision_evaluation.compatibility import compatibility_fingerprint
from experiments.revision_evaluation.contract import (
    Observation,
    RunMetadata,
    RunSummary,
    validate_artifact,
)
from experiments.revision_evaluation.generate_contract import fixture_metadata, fixture_observations
from experiments.revision_evaluation.live import LiveSettings
from experiments.revision_evaluation.planning import ManifestCase, build_plan
from experiments.revision_evaluation.staples import StaplesSnapshot
from experiments.revision_evaluation.transport import CheckpointError

from app.dishes.errors import MODEL_NOT_CONFIGURED, DishLLMError
from app.dishes.llm import DishLLM
from tests.dishes.test_dishes import STAPLES
from tests.dishes.test_revision import GOOD
from tests.dishes.test_revision import store as recipes_store


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Keep production retry decisions while removing waits and real sockets."""

    def forbidden(*args, **kwargs):
        raise AssertionError("real networking is forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setenv("OPENROUTER_API_KEY", "runner-private-key")
    monkeypatch.setattr(live, "DishLLM", lambda *a, **kw: DishLLM(*a, **kw, retry_waits=(0, 0)))


def setup(repetitions=3, *, maximum=20, ingredients=None):
    """Supply explicit synthetic configuration; fixture hashes are test identities only."""
    snapshot = StaplesSnapshot(list(STAPLES))
    catalog, recipes = snapshot.catalog(), recipes_store()
    case = ManifestCase(
        id="runner-case",
        dish_id="kimchi-fried-rice",
        ingredients=["밥", "김치"] if ingredients is None else ingredients,
    )
    plan = build_plan(
        [case], [case.id], repetitions, recipes=recipes, catalog=catalog, snapshot=snapshot
    )
    settings = LiveSettings("fixture/model", maximum)
    metadata = RunMetadata.model_validate(fixture_metadata(fixture_observations()))
    metadata.run_id, metadata.state = "runner-test", "running"
    metadata.plan = list(plan.units)
    metadata.effective_assumed_staples = list(snapshot.names)
    metadata.model, metadata.pricing = settings.model_metadata(), settings.pricing_metadata()
    metadata.http_attempt_budget = metadata.http_attempt_budget.model_validate(
        {"maximum": maximum, "consumed": 0, "remaining": maximum}
    )
    metadata.resume_history = []
    metadata.identities.input_sha256 = {
        case_id: hashlib.sha256(
            json.dumps(
                value.model_dump(),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        for case_id, value in plan.inputs.items()
    }
    metadata.compatibility_fingerprint = compatibility_fingerprint(metadata)
    metadata.plan = []
    return (
        plan,
        metadata,
        dict(
            snapshot=snapshot,
            catalog=catalog,
            recipes=recipes,
            settings=settings,
            allow_live_api=True,
        ),
    )


def answer(data=GOOD):
    """Return deterministic provider metadata without an arbitrary error payload."""
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": json.dumps(data, ensure_ascii=False)},
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 20, "cost": 0.01},
        },
    )


def artifacts(tmp_path):
    root = tmp_path / "runner-test"
    metadata = RunMetadata.model_validate_json((root / "metadata.json").read_text(encoding="utf-8"))
    summary = RunSummary.model_validate_json((root / "summary.json").read_text(encoding="utf-8"))
    observations = [
        Observation.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(root.glob("observations/*/*.json"))
    ]
    for value in (metadata, summary, *observations):
        validate_artifact(value.model_dump(by_alias=True))
    return metadata, summary, observations


def test_sequential_api_and_response_errors_continue_to_fresh_success(tmp_path, monkeypatch):
    plan, metadata, kwargs = setup()
    before = deepcopy((plan, metadata))
    sends, recorders = [], []
    factory = runner.make_live_model

    def record(*a, **kw):
        model = factory(*a, **kw)
        recorders.append(model)
        return model

    def handle(request):
        sends.append(request)
        if len(sends) == 1:
            return httpx.Response(503, json={"error": "private provider body"})
        if len(sends) == 2:
            return httpx.Response(200, json={"choices": [{"message": {"content": "{bad"}}]})
        return answer()

    monkeypatch.setattr(runner, "make_live_model", record)
    result = runner.run_new(
        plan,
        metadata,
        parent=tmp_path,
        transport_factory=lambda: httpx.MockTransport(handle),
        **kwargs,
    )
    saved, summary, observations = artifacts(tmp_path)
    assert summary == result and saved.state == "completed"
    assert [item.execution.terminal_outcome for item in observations] == [
        "api_error",
        "response_error",
        "revised",
    ]
    assert len(sends) == 3 and len({id(item) for item in recorders}) == 3
    assert [len(item.calls) for item in recorders] == [1, 1, 1]
    assert summary.totals.completed_repetitions == 3
    assert summary.json_parse_success.numerator == 1 and summary.json_parse_success.denominator == 2
    assert observations[-1].deterministic_evaluation.deleted_ingredient_explanation.denominator == 2
    assert all(unit.state == "completed" for unit in saved.plan)
    assert (plan, metadata) == before
    assert "private provider body" not in "".join(
        path.read_text(encoding="utf-8") for path in (tmp_path / "runner-test").rglob("*.json")
    )


@pytest.mark.parametrize(
    "ingredients,outcome", [(["밥", "김치", "대파", "계란"], "unchanged"), (["밥"], "refused")]
)
def test_zero_call_production_branches(tmp_path, ingredients, outcome):
    plan, metadata, kwargs = setup(2, ingredients=ingredients)

    def unexpected(request):
        raise AssertionError("no-call branch sent a request")

    runner.run_new(
        plan,
        metadata,
        parent=tmp_path,
        transport_factory=lambda: httpx.MockTransport(unexpected),
        **kwargs,
    )
    saved, summary, observations = artifacts(tmp_path)
    assert saved.state == "completed" and summary.totals.http_attempts == 0
    assert [item.execution.terminal_outcome for item in observations] == [outcome, outcome]


def test_reask_is_within_one_repetition_and_next_recorder_starts_initial(tmp_path):
    plan, metadata, kwargs = setup(2)
    sends = []

    def handle(request):
        sends.append(json.loads(request.content))
        return answer({**GOOD, "changes": []}) if len(sends) == 1 else answer()

    runner.run_new(
        plan,
        metadata,
        parent=tmp_path,
        transport_factory=lambda: httpx.MockTransport(handle),
        **kwargs,
    )
    _, summary, observations = artifacts(tmp_path)
    assert summary.totals.reasks == 1 and summary.totals.http_attempts == 3
    assert [[call.purpose for call in item.model_calls] for item in observations] == [
        ["initial", "reask"],
        ["initial"],
    ]


@pytest.mark.parametrize(
    "failure", ["budget", "pre_write", "post_write", "interrupt", "configuration"]
)
def test_operational_stop_never_starts_later_repetition(tmp_path, monkeypatch, failure):
    plan, metadata, kwargs = setup(maximum=1 if failure == "budget" else 20)
    sends = []
    original = runner._EvaluatedStore._write

    def write(self, relative, value):
        stage = value.get("execution", {}).get("checkpoint_stage")
        if (failure, stage) in (
            ("pre_write", "request_prepared"),
            ("post_write", "response_received"),
        ):
            raise OSError("runner-private-key")
        return original(self, relative, value)

    def handle(request):
        sends.append(request)
        if failure == "interrupt":
            raise KeyboardInterrupt()
        return httpx.Response(429) if failure == "budget" else answer()

    if failure == "configuration":

        def unconfigured(*a, **kw):
            raise DishLLMError(MODEL_NOT_CONFIGURED)

        monkeypatch.setattr(runner, "make_live_model", unconfigured)
    monkeypatch.setattr(runner._EvaluatedStore, "_write", write)
    expected = (
        KeyboardInterrupt
        if failure == "interrupt"
        else DishLLMError
        if failure == "configuration"
        else CheckpointError
    )
    with pytest.raises(expected):
        runner.run_new(
            plan,
            metadata,
            parent=tmp_path,
            transport_factory=lambda: httpx.MockTransport(handle),
            **kwargs,
        )
    saved, summary, observations = artifacts(tmp_path)
    assert saved.state == "interrupted" and not summary.complete
    assert len(observations) == 1 and observations[0].execution.terminal_outcome is None
    assert [unit.state for unit in saved.plan] == ["incomplete", "not_started", "not_started"]
    assert len(sends) == (0 if failure in ("pre_write", "configuration") else 1)
    assert saved.http_attempt_budget.consumed == len(sends)
    if failure in ("post_write", "interrupt"):
        assert observations[0].model_calls[0].http_attempts[0].delivery == "unknown"


def test_no_opt_in_or_changed_configuration_creates_no_run(tmp_path):
    plan, metadata, kwargs = setup()
    kwargs["allow_live_api"] = False
    with pytest.raises(ValueError, match="opt-in"):
        runner.run_new(plan, metadata, parent=tmp_path, **kwargs)
    kwargs["allow_live_api"] = True
    metadata.model["id"] = "changed"
    with pytest.raises(ValueError, match="configuration"):
        runner.run_new(plan, metadata, parent=tmp_path, **kwargs)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("change", ["mismatch", "missing", "extra", "plan_input"])
def test_input_hash_mismatch_fails_before_storage_or_model_construction(
    tmp_path, monkeypatch, change
):
    plan, metadata, kwargs = setup()
    if change == "mismatch":
        metadata.identities.input_sha256["runner-case"] = "0" * 64
    elif change == "missing":
        metadata.identities.input_sha256.clear()
    elif change == "extra":
        metadata.identities.input_sha256["unexpected-case"] = "0" * 64
    else:
        plan.inputs["runner-case"].supplied_ingredients.append("소금")
    # Keep metadata internally consistent: the new check must bind its hashes
    # to plan contents, not merely rediscover a broken metadata fingerprint.
    full = metadata.model_copy(deep=True)
    full.plan = list(plan.units)
    metadata.compatibility_fingerprint = compatibility_fingerprint(full)

    def unexpected(*args, **kwargs):
        raise AssertionError("input mismatch reached storage or model construction")

    monkeypatch.setattr(runner, "_EvaluatedStore", unexpected)
    monkeypatch.setattr(runner, "make_live_model", unexpected)
    with pytest.raises(ValueError, match="metadata input hashes"):
        runner.run_new(plan, metadata, parent=tmp_path, **kwargs)
    assert not list(tmp_path.iterdir())


def test_later_failure_preserves_earlier_completed_bytes_and_known_cost(tmp_path, monkeypatch):
    plan, metadata, kwargs = setup()
    original = runner._EvaluatedStore._write
    first_bytes, sends = [], []
    first = tmp_path / "runner-test/observations/runner-case__r01/attempt-001.json"

    def write(self, relative, value):
        if (
            value.get("repetition") == 2
            and value.get("execution", {}).get("checkpoint_stage") == "response_received"
        ):
            raise OSError("failed later response write")
        return original(self, relative, value)

    def handle(request):
        if sends:
            first_bytes.append(first.read_bytes())
        sends.append(request)
        return answer()

    monkeypatch.setattr(runner._EvaluatedStore, "_write", write)
    with pytest.raises(CheckpointError):
        runner.run_new(
            plan,
            metadata,
            parent=tmp_path,
            transport_factory=lambda: httpx.MockTransport(handle),
            **kwargs,
        )
    saved, summary, observations = artifacts(tmp_path)
    assert len(sends) == 2 and first.read_bytes() == first_bytes[0]
    assert [unit.state for unit in saved.plan] == ["completed", "incomplete", "not_started"]
    assert summary.totals.completed_repetitions == 1 and summary.totals.incomplete_attempts == 1
    assert summary.totals.http_attempts == 2
    assert (
        summary.totals.cost_usd.value is None and summary.totals.cost_usd.confirmed_subtotal == 0.01
    )
    assert observations[-1].model_calls[0].http_attempts[0].delivery == "unknown"


@pytest.mark.parametrize("boundary", ["terminal", "summary.json"])
def test_terminal_or_summary_publication_failure_stops_before_next_repetition(
    tmp_path, monkeypatch, boundary
):
    plan, metadata, kwargs = setup()
    original = runner._EvaluatedStore._write
    sends, failed = [], []

    def write(self, relative, value):
        target = value.get("execution", {}).get("checkpoint_stage") == boundary
        # Fail a summary write only after the first terminal result exists.
        target = target or (
            relative == boundary and value.get("totals", {}).get("completed_repetitions") == 1
        )
        if target and not failed:
            failed.append(True)
            raise OSError("runner-private-key")
        return original(self, relative, value)

    monkeypatch.setattr(runner._EvaluatedStore, "_write", write)
    with pytest.raises(CheckpointError if boundary == "terminal" else OSError):
        runner.run_new(
            plan,
            metadata,
            parent=tmp_path,
            transport_factory=lambda: httpx.MockTransport(
                lambda request: sends.append(request) or answer()
            ),
            **kwargs,
        )
    saved, summary, _ = artifacts(tmp_path)
    assert len(sends) == 1 and saved.state == "interrupted"
    assert summary.totals.completed_repetitions == (0 if boundary == "terminal" else 1)
    assert saved.plan[1].state == "not_started"
