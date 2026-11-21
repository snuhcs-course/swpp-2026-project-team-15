# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Mock in-place resume checks for immutable attempts, cumulative spending and compatibility."""

import json
from copy import deepcopy

import httpx
import pytest
from experiments.revision_evaluation import runner
from experiments.revision_evaluation.budgeting import (
    BudgetedRunStore,
    BudgetExceeded,
    read_run_budget,
)
from experiments.revision_evaluation.live import LiveSettings
from experiments.revision_evaluation.persistence import PersistenceError
from experiments.revision_evaluation.staples import StaplesSnapshot
from experiments.revision_evaluation.telemetry import TokenPrices

from tests.experiments.revision_evaluation.test_runner import answer, artifacts, setup
from tests.experiments.revision_evaluation.test_runner import no_network as no_network


def files(root):
    """Compare actual artifact bytes, not just reconstructed model equality."""
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*.json")}


def interrupted_run(tmp_path, monkeypatch, boundary="request_prepared", *, maximum=20):
    """Complete two repetitions, then simulate an abrupt third stop with lagging metadata."""
    plan, metadata, kwargs = setup(maximum=maximum)
    original_write = runner._EvaluatedStore._write
    original_progress = runner._publish_progress
    sends = []

    def write(self, relative, value):
        original_write(self, relative, value)
        if (
            value.get("repetition") == 3
            and value.get("execution", {}).get("checkpoint_stage") == boundary
        ):
            raise KeyboardInterrupt()

    def progress(store, *, state):
        if state == "interrupted":
            # A hard stop cannot publish a graceful final metadata refresh.
            raise OSError("process stopped")
        return original_progress(store, state=state)

    def handle(request):
        sends.append(request)
        if boundary == "during_send" and len(sends) == 3:
            raise KeyboardInterrupt()
        return answer()

    with monkeypatch.context() as scoped:
        scoped.setattr(runner._EvaluatedStore, "_write", write)
        scoped.setattr(runner, "_publish_progress", progress)
        with pytest.raises(KeyboardInterrupt):
            runner.run_new(
                plan,
                metadata,
                parent=tmp_path,
                transport_factory=lambda: httpx.MockTransport(handle),
                **kwargs,
            )
    return plan, metadata, kwargs, sends


@pytest.mark.parametrize("boundary", ["request_prepared", "during_send", "response_received"])
def test_resume_skips_completed_and_preserves_all_earlier_attempt_bytes(
    tmp_path, monkeypatch, boundary
):
    plan, seed, kwargs, prior_sends = interrupted_run(tmp_path, monkeypatch, boundary)
    root = tmp_path / seed.run_id
    before = files(root)
    durable = read_run_budget(root)
    assert durable.metadata.http_attempt_budget.consumed == 2
    assert durable.budget.consumed == 3
    sends = []
    result = runner.run_resume(
        root,
        plan,
        seed.identities,
        seed.code_identity,
        transport_factory=lambda: httpx.MockTransport(
            lambda request: sends.append(request) or answer()
        ),
        **kwargs,
    )
    saved, summary, observations = artifacts(tmp_path)
    assert result == summary and summary.complete and saved.state == "completed"
    assert len(prior_sends) == (2 if boundary == "request_prepared" else 3)
    assert len(sends) == 1
    after = files(root)
    for ref, content in before.items():
        if ref.startswith("observations/"):
            assert after[ref] == content
    assert [(item.repetition, item.execution_attempt) for item in observations] == [
        (1, 1),
        (2, 1),
        (3, 1),
        (3, 2),
    ]
    assert observations[2].execution.state == "running"
    assert observations[2].execution.terminal_outcome is None
    assert [unit.selected_completed_attempt for unit in saved.plan] == [1, 1, 2]
    assert len(saved.plan[-1].observation_refs) == 2
    assert saved.plan[-1].cumulative_telemetry.http_attempts == 2
    assert saved.http_attempt_budget.consumed == summary.totals.http_attempts == 4
    assert saved.http_attempt_budget.maximum == 20 and saved.http_attempt_budget.remaining == 16
    assert summary.totals.completed_repetitions == 3 and summary.totals.incomplete_attempts == 1
    assert len(saved.resume_history) == 1 and saved.resume_history[0]["from_execution_attempt"] == 1
    if boundary == "response_received":
        assert summary.totals.cost_usd.provenance == "measured"
        assert summary.totals.cost_usd.value == pytest.approx(0.04)
        assert summary.totals.tokens.input_tokens.value == 40
    else:
        assert summary.totals.cost_usd.provenance == "missing"
        assert summary.totals.cost_usd.confirmed_subtotal == pytest.approx(0.03)
        assert summary.totals.tokens.input_tokens.value is None
        assert summary.totals.tokens.input_tokens.confirmed_subtotal == 30


def test_second_resume_uses_attempt_three_without_resetting_cap(tmp_path, monkeypatch):
    plan, seed, kwargs, _ = interrupted_run(tmp_path, monkeypatch, maximum=5)
    root = tmp_path / seed.run_id

    def stop(request):
        raise KeyboardInterrupt()

    with pytest.raises(KeyboardInterrupt):
        runner.run_resume(
            root,
            plan,
            seed.identities,
            seed.code_identity,
            transport_factory=lambda: httpx.MockTransport(stop),
            **kwargs,
        )
    before = {
        ref: content for ref, content in files(root).items() if ref.startswith("observations/")
    }
    assert read_run_budget(root).budget.consumed == 4
    result = runner.run_resume(
        root,
        plan,
        seed.identities,
        seed.code_identity,
        transport_factory=lambda: httpx.MockTransport(lambda request: answer()),
        **kwargs,
    )
    assert result.totals.http_attempts == 5 and result.totals.incomplete_attempts == 2
    saved, _, observations = artifacts(tmp_path)
    assert saved.http_attempt_budget.maximum == 5 and saved.http_attempt_budget.remaining == 0
    assert saved.plan[-1].selected_completed_attempt == 3 and len(saved.resume_history) == 2
    assert len(observations) == 5
    assert all(files(root)[ref] == content for ref, content in before.items())


@pytest.mark.parametrize(
    "change",
    [
        "model",
        "prices",
        "cap",
        "code",
        "input_hash",
        "plan_input",
        "stored_input",
        "missing",
        "corrupt",
        "completed",
        "no_opt_in",
    ],
)
def test_incompatible_or_invalid_resume_is_read_only(tmp_path, monkeypatch, change):
    plan, seed, kwargs, _ = interrupted_run(tmp_path, monkeypatch)
    root = tmp_path / seed.run_id
    identities, code = deepcopy(seed.identities), deepcopy(seed.code_identity)
    if change == "model":
        kwargs["settings"] = LiveSettings("other/model", 20)
    elif change == "prices":
        kwargs["settings"] = LiveSettings("fixture/model", 20, TokenPrices(1, 2))
    elif change == "cap":
        kwargs["settings"] = LiveSettings("fixture/model", 21)
    elif change == "code":
        code.tree = "0" * 40
    elif change == "input_hash":
        identities.input_sha256["runner-case"] = "0" * 64
    elif change == "plan_input":
        plan.inputs["runner-case"].supplied_ingredients.append("소금")
    elif change == "stored_input":
        path = root / "observations/runner-case__r03/attempt-001.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["input"]["supplied_ingredients"].append("소금")
        path.write_text(json.dumps(raw), encoding="utf-8")
    elif change == "missing":
        (root / "observations/runner-case__r01/attempt-001.json").unlink()
    elif change == "corrupt":
        (root / "observations/runner-case__r03/attempt-001.json").write_text(
            "{bad", encoding="utf-8"
        )
    elif change == "completed":
        path = root / "metadata.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["state"] = "completed"
        path.write_text(json.dumps(raw), encoding="utf-8")
    else:
        kwargs["allow_live_api"] = False
    before = files(root)

    def unexpected(*args, **kwargs):
        raise AssertionError("invalid resume reached model/store opening")

    monkeypatch.setattr(runner, "make_live_model", unexpected)
    monkeypatch.setattr(runner._EvaluatedStore, "open_existing", unexpected)
    with pytest.raises((ValueError, PersistenceError)):
        runner.run_resume(root, plan, identities, code, **kwargs)
    assert files(root) == before


def test_exhausted_budget_and_missing_root_are_read_only(tmp_path, monkeypatch):
    plan, seed, kwargs, _ = interrupted_run(tmp_path, monkeypatch, maximum=3)
    root = tmp_path / seed.run_id
    before = files(root)
    with pytest.raises(BudgetExceeded):
        runner.run_resume(root, plan, seed.identities, seed.code_identity, **kwargs)
    assert files(root) == before
    with pytest.raises(PersistenceError):
        runner.run_resume(tmp_path / "missing", plan, seed.identities, seed.code_identity, **kwargs)
    assert not (tmp_path / "missing").exists()


def test_open_existing_is_read_only_and_freezes_old_running_attempts(tmp_path, monkeypatch):
    _, seed, kwargs, _ = interrupted_run(tmp_path, monkeypatch)
    root = tmp_path / seed.run_id
    before = files(root)
    store = BudgetedRunStore.open_existing(root, snapshot=kwargs["snapshot"], maximum=20)
    previous = read_run_budget(root).observations[-1].model_copy(deep=True)
    previous.execution.checkpoint_revision += 1
    with pytest.raises(ValueError, match="pre-resume attempts"):
        store.write_observation(previous)
    with pytest.raises(PersistenceError):
        BudgetedRunStore(tmp_path, seed.run_id, maximum=20, snapshot=kwargs["snapshot"])
    with pytest.raises(PersistenceError):
        BudgetedRunStore.open_existing(root, snapshot=kwargs["snapshot"], maximum=21)
    with pytest.raises(ValueError):
        BudgetedRunStore.open_existing(root, snapshot=StaplesSnapshot([]), maximum=20)
    with pytest.raises(ValueError, match="redaction"):
        BudgetedRunStore.open_existing(
            root, snapshot=kwargs["snapshot"], maximum=20, secrets=(kwargs["snapshot"].names[0],)
        )
    assert files(root) == before
