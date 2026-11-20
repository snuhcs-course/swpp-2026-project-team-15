"""Offline tests for the frozen Revision evaluation v1 JSON contract."""

import json
from copy import deepcopy

import pytest
from experiments.revision_evaluation.contract import (
    OBSERVATION_SCHEMA,
    ContractVersionError,
    Observation,
    OptionalNumber,
    Rate,
    fixture_root,
    schema_document,
    validate_artifact,
    validate_fixture_bundle,
)
from experiments.revision_evaluation.generate_contract import (
    fixture_metadata,
    fixture_observations,
    fixture_summary,
)
from pydantic import ValidationError


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_committed_schema_and_fixtures_are_generated_deterministically():
    root = fixture_root()
    observations = fixture_observations()
    assert read_json(root.parent.parent / "schema.json") == schema_document()
    assert read_json(root / "metadata.json") == fixture_metadata(observations)
    assert read_json(root / "summary.json") == fixture_summary(observations)
    for relative, expected in observations.items():
        assert read_json(root / "observations" / relative) == expected


def test_fixture_bundle_validates_and_relative_references_resolve():
    metadata, observations, summary = validate_fixture_bundle()
    assert metadata.run_id == summary.run_id
    assert len(observations) == 9
    assert len(summary.observation_refs) == 9


def test_fixture_bundle_covers_terminal_and_interrupted_paths():
    _, observations, _ = validate_fixture_bundle()
    outcomes = {
        observation.execution.terminal_outcome
        for observation in observations
        if observation.execution.state == "completed"
    }
    assert outcomes == {
        "unchanged",
        "revised",
        "refused",
        "check_failed",
        "response_error",
        "api_error",
    }
    interrupted = [value for value in observations if value.execution.state == "interrupted"]
    assert len(interrupted) == 1
    assert interrupted[0].execution.checkpoint_stage == "request_prepared"


def test_unknown_contract_version_is_rejected_explicitly():
    value = read_json(fixture_root() / "observations/unchanged__r01/attempt-001.json")
    value["artifact_schema"] = "revision-evaluation-observation/v2"
    with pytest.raises(ContractVersionError, match="unsupported artifact schema"):
        validate_artifact(value)


def test_null_zero_and_not_applicable_are_distinct():
    zero = OptionalNumber.model_validate({"applicability": "value", "value": 0})
    unavailable = OptionalNumber.model_validate({"applicability": "unavailable", "value": None})
    not_applicable = OptionalNumber.model_validate(
        {"applicability": "not_applicable", "value": None}
    )
    assert zero.value == 0
    assert unavailable.applicability != not_applicable.applicability
    assert Rate.model_validate({"numerator": 0, "denominator": 0, "value": None}).value is None
    with pytest.raises(ValidationError):
        OptionalNumber.model_validate({"applicability": "unavailable", "value": 0})


def test_prepared_unknown_request_consumes_http_attempt_budget():
    metadata, observations, summary = validate_fixture_bundle()
    prepared = [
        attempt
        for observation in observations
        for call in observation.model_calls
        for attempt in call.http_attempts
        if attempt.state == "request_prepared"
    ]
    assert len(prepared) == 1
    assert prepared[0].delivery == "unknown" and prepared[0].counts_against_budget is True
    assert metadata.http_attempt_budget.consumed == summary.totals.http_attempts
    assert metadata.http_attempt_budget.consumed == sum(
        observation.telemetry.http_attempts for observation in observations
    )


def test_checkpoint_and_execution_attempt_numbers_are_positive():
    value = read_json(fixture_root() / "observations/resumed__r03/attempt-001.json")
    for path in (("execution_attempt",), ("execution", "checkpoint_revision")):
        invalid = deepcopy(value)
        target = invalid
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = 0
        with pytest.raises(ValidationError):
            Observation.model_validate(invalid)


def test_http_attempt_numbers_are_contiguous_per_logical_call():
    value = read_json(fixture_root() / "observations/revised-after-reask-429__r01/attempt-001.json")
    value["model_calls"][0]["http_attempts"][1]["index"] = 3
    with pytest.raises(ValidationError, match="one-based and contiguous"):
        Observation.model_validate(value)


def test_fixture_only_consumer_can_find_judge_source_fields_without_runner_imports():
    root = fixture_root()
    metadata = read_json(root / "metadata.json")
    summary = read_json(root / "summary.json")
    selected = next(unit for unit in metadata["plan"] if unit["case_id"] == "resumed")
    final_ref = selected["observation_refs"][selected["selected_completed_attempt"] - 1]
    observation = read_json(root / final_ref)
    assert observation["artifact_schema"] == OBSERVATION_SCHEMA
    assert observation["input"]["original_recipe"]["ingredients"]
    assert observation["execution"]["final_service_response"]["status"] == "revised"
    assert "checks" in observation and "telemetry" in observation
    assert final_ref in summary["observation_refs"]
