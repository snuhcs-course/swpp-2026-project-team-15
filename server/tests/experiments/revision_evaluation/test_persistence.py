# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Disposable-filesystem tests of atomic attempt and metadata persistence."""

import json

import pytest
from experiments.revision_evaluation import persistence
from experiments.revision_evaluation.contract import Observation, RunMetadata
from experiments.revision_evaluation.generate_contract import fixture_metadata, fixture_observations
from experiments.revision_evaluation.persistence import PersistenceError, RunStore


def attempt(case="unchanged", *, running=False):
    """Return a fixture adapted to one local test run, optionally as an active checkpoint."""
    key = "resumed__r03/attempt-001.json" if running else f"{case}__r01/attempt-001.json"
    value = fixture_observations()[key]
    value["run_id"] = "test-run"
    if running:
        value["execution"].update(state="running", checkpoint_revision=1)
    return Observation.model_validate(value)


def metadata(units):
    """Build contract-valid test metadata with explicit saved/not-started plan units."""
    value = fixture_metadata(fixture_observations())
    value.update(run_id="test-run", state="running", plan=units)
    return RunMetadata.model_validate(value)


def unit(value, reference, state):
    """Index the exact persisted attempt without inventing cumulative measurements."""
    return {
        "case_id": value.case_id,
        "repetition": value.repetition,
        "state": state,
        "observation_refs": [reference] if reference else [],
        "selected_completed_attempt": value.execution_attempt if state == "completed" else None,
        "cumulative_telemetry": value.telemetry.model_dump() if reference else None,
    }


@pytest.mark.parametrize(
    "run_id", ["", "..", "../escape", "a/b", "a\\b", "C:drive", "CON", "nul", "COM1", "a" * 65]
)
def test_unsafe_run_names_are_rejected_before_directory_creation(tmp_path, run_id):
    with pytest.raises(ValueError, match="run ID"):
        RunStore(tmp_path, run_id)
    assert list(tmp_path.iterdir()) == []


def test_existing_run_cannot_be_overwritten(tmp_path):
    RunStore(tmp_path, "test-run")
    with pytest.raises(PersistenceError, match="new run"):
        RunStore(tmp_path, "test-run")


def test_active_attempt_replacement_is_contract_valid_and_terminal_attempt_is_immutable(tmp_path):
    store = RunStore(tmp_path, "test-run")
    value = attempt(running=True)
    reference = store.write_observation(value)
    value.execution.checkpoint_revision += 1
    value.execution.state = "interrupted"
    assert store.write_observation(value) == reference
    saved = Observation.model_validate_json((store.root / reference).read_text(encoding="utf-8"))
    assert saved.execution.checkpoint_revision == 2
    with pytest.raises(ValueError, match="immutable"):
        store.write_observation(value)


@pytest.mark.parametrize("operation", ["replace", "fsync"])
def test_failed_later_write_preserves_old_attempt_bytes_and_removes_temporary_files(
    tmp_path, monkeypatch, operation
):
    store = RunStore(tmp_path, "test-run")
    earlier = store.write_observation(attempt())
    active = attempt(running=True)
    reference = store.write_observation(active)
    earlier_bytes = (store.root / earlier).read_bytes()
    active_bytes = (store.root / reference).read_bytes()

    def fail(*args):
        raise OSError("Authorization: Bearer private-storage-detail")

    monkeypatch.setattr(persistence.os, operation, fail)
    active.execution.checkpoint_revision += 1
    with pytest.raises(PersistenceError, match="^could not persist artifact$"):
        store.write_observation(active)
    assert (store.root / earlier).read_bytes() == earlier_bytes
    assert (store.root / reference).read_bytes() == active_bytes
    assert list(store.root.rglob("*.tmp")) == []
    assert json.loads(active_bytes)["execution"]["state"] == "running"


def test_metadata_lists_completed_incomplete_and_not_started_units_accurately(tmp_path):
    store = RunStore(tmp_path, "test-run", secrets=("configured-private-value",))
    completed, active, pending = attempt(), attempt(running=True), attempt("check-failed")
    complete_ref = store.write_observation(completed)
    active_ref = store.write_observation(active)
    data = metadata(
        [
            unit(completed, complete_ref, "completed"),
            unit(active, active_ref, "incomplete"),
            unit(pending, None, "not_started"),
        ]
    )
    data.model.update(api_key="credential", nested={"note": "configured-private-value"})
    before = data.model_dump()
    store.write_metadata(data)
    saved_text = (store.root / "metadata.json").read_text(encoding="utf-8")
    saved = RunMetadata.model_validate_json(saved_text)
    assert [item.state for item in saved.plan] == ["completed", "incomplete", "not_started"]
    assert saved.plan[0].selected_completed_attempt == 1
    assert saved.plan[1].selected_completed_attempt is None
    assert "configured-private-value" not in saved_text and "credential" not in saved_text
    assert saved.model["api_key"] == "[REDACTED]"
    assert data.model_dump() == before


def test_failed_metadata_replacement_preserves_previous_plan(tmp_path, monkeypatch):
    store = RunStore(tmp_path, "test-run")
    completed, pending = attempt(), attempt("check-failed")
    reference = store.write_observation(completed)
    data = metadata([unit(completed, reference, "completed"), unit(pending, None, "not_started")])
    store.write_metadata(data)
    before = (store.root / "metadata.json").read_bytes()

    def fail(*args):
        raise OSError("private detail")

    monkeypatch.setattr(persistence.os, "replace", fail)
    with pytest.raises(PersistenceError):
        store.write_metadata(data)
    assert (store.root / "metadata.json").read_bytes() == before
    assert (store.root / reference).is_file()


def test_stale_plan_state_is_rejected_before_metadata_publication(tmp_path):
    store = RunStore(tmp_path, "test-run")
    value = attempt()
    reference = store.write_observation(value)
    with pytest.raises(ValueError, match="plan state"):
        store.write_metadata(metadata([unit(value, reference, "incomplete")]))
    assert not (store.root / "metadata.json").exists()


def test_case_paths_are_portable_and_preserve_original_case_ids(tmp_path):
    store = RunStore(tmp_path, "test-run")
    value = attempt()
    value.case_id = "egg-roll:a"
    first = store.write_observation(value)
    assert ":" not in first
    assert json.loads((store.root / first).read_text(encoding="utf-8"))["case_id"] == "egg-roll:a"
    value.case_id = "egg-roll/a"
    assert store.write_observation(value) != first


def test_checkpoint_revisions_must_increase(tmp_path):
    store = RunStore(tmp_path, "test-run")
    value = attempt(running=True)
    store.write_observation(value)
    with pytest.raises(ValueError, match="revision must increase"):
        store.write_observation(value)


def _recount(value):
    """Keep modified checkpoints contract-valid so tests exercise storage guards."""
    calls = value["model_calls"]
    attempts = [row for call in calls for row in call["http_attempts"]]
    value["telemetry"].update(
        logical_calls=len(calls),
        reasks=sum(call["purpose"] == "reask" for call in calls),
        http_attempts=len(attempts),
        http_429_responses=sum(row["status_code"] == 429 for row in attempts),
        http_429_retries=sum(
            row["status_code"] == 429 for call in calls for row in call["http_attempts"][:-1]
        ),
    )
    return Observation.model_validate(value)


@pytest.mark.parametrize(
    "change",
    [
        "remove_call",
        "remove_http",
        "request",
        "prepared_at",
        "http_state",
        "response",
        "usage",
        "cost",
        "parsing",
        "decoded",
        "input",
        "started_at",
        "remove_check",
        "replace_check",
        "remove_finding",
        "replace_finding",
        "coverage",
    ],
)
def test_running_update_cannot_erase_or_replace_recorded_evidence(tmp_path, change):
    store = RunStore(tmp_path, "test-run")
    value = attempt("revised-after-reask-429").model_dump(by_alias=True)
    value["execution"].update(state="running", terminal_outcome=None, outcome_source=None)
    reference = store.write_observation(Observation.model_validate(value))
    before = (store.root / reference).read_bytes()
    value["execution"]["checkpoint_revision"] += 1
    call = value["model_calls"][0]
    http = call["http_attempts"][1]
    if change == "remove_call":
        value["model_calls"].pop()
    elif change == "remove_http":
        call["http_attempts"].pop()
    elif change == "request":
        call["request"]["user"] = "replacement request"
    elif change == "prepared_at":
        http["prepared_at"] = "different timestamp"
    elif change == "http_state":
        replacement = attempt(running=True).model_calls[0].http_attempts[0].model_dump()
        replacement["index"] = 2
        call["http_attempts"][1] = replacement
    elif change == "response":
        http["safe_response_text"] = None
    elif change == "usage":
        http["usage"] = None
    elif change == "cost":
        http["cost_usd"].update(value=0, confirmed_subtotal=0)
    elif change == "parsing":
        call["parsing"].update(attempted=False, succeeded=None, error=None)
    elif change == "decoded":
        call["decoded_answer"]["ingredients"] = []
    elif change == "input":
        value["input"]["supplied_ingredients"] = []
    elif change == "started_at":
        value["execution"]["started_at"] = "different timestamp"
    elif change == "remove_check":
        value["checks"].pop()
    elif change == "replace_check":
        value["checks"][0]["message"] = "replacement decision"
    elif change == "remove_finding":
        value["deterministic_evaluation"]["answers"].pop()
    elif change == "replace_finding":
        value["deterministic_evaluation"]["answers"][0]["reference_valid"] = False
    elif change == "coverage":
        value["deterministic_evaluation"]["deleted_ingredient_explanation"].update(
            numerator=0, denominator=0, value=None
        )
    updated = _recount(value)
    with pytest.raises(ValueError, match="recorded|cannot change"):
        store.write_observation(updated)
    assert (store.root / reference).read_bytes() == before


@pytest.mark.parametrize("terminal", ["response_received", "transport_error"])
def test_prepared_request_can_acquire_a_result_without_changing_its_identity(tmp_path, terminal):
    store = RunStore(tmp_path, "test-run")
    active = attempt(running=True)
    reference = store.write_observation(active)
    value = active.model_dump(by_alias=True)
    fixture = attempt("api-error") if terminal == "transport_error" else attempt("check-failed")
    value["model_calls"] = [fixture.model_calls[0].model_dump(by_alias=True)]
    value["execution"].update(checkpoint_revision=2, checkpoint_stage="response_received")
    value["deterministic_evaluation"]["answers"] = [
        fixture.deterministic_evaluation.answers[0].model_dump()
    ]
    assert store.write_observation(_recount(value)) == reference
    saved = Observation.model_validate_json((store.root / reference).read_text(encoding="utf-8"))
    assert saved.model_calls[0].http_attempts[0].state == terminal


@pytest.mark.parametrize("field", ["prepared_at", "request_sha256", "model"])
def test_prepared_request_identity_cannot_be_replaced(tmp_path, field):
    store = RunStore(tmp_path, "test-run")
    active = attempt(running=True)
    reference = store.write_observation(active)
    before = (store.root / reference).read_bytes()
    value = active.model_dump(by_alias=True)
    value["execution"]["checkpoint_revision"] += 1
    value["model_calls"][0]["http_attempts"][0][field] = (
        "b" * 64 if field == "request_sha256" else "replacement"
    )
    with pytest.raises(ValueError, match="prepared HTTP request cannot change"):
        store.write_observation(Observation.model_validate(value))
    assert (store.root / reference).read_bytes() == before


def test_running_update_can_append_http_attempts_calls_and_checks(tmp_path):
    store = RunStore(tmp_path, "test-run")
    value = attempt("revised-after-reask-429").model_dump(by_alias=True)
    value["execution"].update(state="running", terminal_outcome=None, outcome_source=None)
    initial = json.loads(json.dumps(value))
    initial["model_calls"] = initial["model_calls"][:1]
    initial["model_calls"][0]["http_attempts"] = initial["model_calls"][0]["http_attempts"][:1]
    initial["model_calls"][0]["parsing"].update(attempted=False, succeeded=None)
    initial["model_calls"][0]["decoded_answer"] = None
    initial["checks"] = []
    initial["deterministic_evaluation"]["answers"] = []
    initial["deterministic_evaluation"]["deleted_ingredient_explanation"].update(
        numerator=0, denominator=0, value=None
    )
    reference = store.write_observation(_recount(initial))
    value["execution"]["checkpoint_revision"] += 1
    assert store.write_observation(Observation.model_validate(value)) == reference
    saved = Observation.model_validate_json((store.root / reference).read_text(encoding="utf-8"))
    assert len(saved.model_calls) == 2
    assert len(saved.model_calls[0].http_attempts) == 2
    assert saved.checks == Observation.model_validate(value).checks


def test_parsed_checkpoint_can_fill_decoded_answer_and_unknown_findings(tmp_path):
    store = RunStore(tmp_path, "test-run")
    value = attempt("check-failed").model_dump(by_alias=True)
    value["execution"].update(state="running", terminal_outcome=None, outcome_source=None)
    initial = json.loads(json.dumps(value))
    initial["model_calls"][0]["decoded_answer"] = None
    initial["deterministic_evaluation"]["answers"][0].update(
        structure_valid=None, reference_valid=None
    )
    reference = store.write_observation(Observation.model_validate(initial))
    value["execution"]["checkpoint_revision"] += 1
    assert store.write_observation(Observation.model_validate(value)) == reference
    saved = Observation.model_validate_json((store.root / reference).read_text(encoding="utf-8"))
    assert saved.model_calls[0].decoded_answer == value["model_calls"][0]["decoded_answer"]
    assert saved.deterministic_evaluation.answers[0].structure_valid is True


def test_metadata_reference_cannot_escape_the_run(tmp_path):
    store = RunStore(tmp_path, "test-run")
    with pytest.raises(ValueError, match="inside the run"):
        store.write_metadata(metadata([unit(attempt(), "../outside.json", "completed")]))
