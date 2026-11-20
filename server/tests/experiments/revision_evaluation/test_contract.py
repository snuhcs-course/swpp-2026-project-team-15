# AI-assisted with Codex, 2026-11-20; reviewed by Soohyun An
"""Offline tests for the frozen Revision evaluation v1 JSON contract."""

import json
from copy import deepcopy

import pytest
from experiments.revision_evaluation.contract import (
    OBSERVATION_SCHEMA,
    ContractVersionError,
    Cost,
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

from app.dishes.schemas import ReviseResponse


def read_json(path):
    """Read an artifact as an external JSON consumer would."""

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


def test_successful_revision_fixture_contains_a_checked_meaningful_recipe():
    value = read_json(
        fixture_root()
        / "observations/revised-after-reask-429__r01/attempt-001.json"
    )
    initial, final = value["model_calls"]
    assert initial["decoded_answer"]["changes"] == []
    initial_text = initial["http_attempts"][1]["safe_response_text"]
    assert json.loads(initial_text) == initial["decoded_answer"]
    assert value["checks"][0]["code"] == "unexplained_change"
    assert final["decoded_answer"]["ingredients"]
    assert final["decoded_answer"]["steps"]
    assert final["decoded_answer"]["changes"][0]["ingredient_refs"] == [2]
    assert all(row["name"] != "대파" for row in final["decoded_answer"]["ingredients"])
    assert json.loads(final["http_attempts"][0]["safe_response_text"]) == final["decoded_answer"]

    response = value["execution"]["final_service_response"]
    assert response["revised"]["ingredients"] == final["decoded_answer"]["ingredients"]
    assert response["changes"] == final["decoded_answer"]["changes"]
    assert value["deterministic_evaluation"]["deleted_ingredient_explanation"] == {
        "numerator": 1,
        "denominator": 1,
        "value": 1.0,
    }
    assert read_json(fixture_root() / "summary.json")["explanation_coverage"] == {
        "numerator": 2,
        "denominator": 2,
        "value": 1.0,
    }


def test_unchanged_fixture_preserves_the_complete_no_call_service_response():
    value = read_json(fixture_root() / "observations/unchanged__r01/attempt-001.json")
    response = value["execution"]["final_service_response"]
    source = value["input"]["original_recipe"]
    assert value["execution"]["terminal_outcome"] == "unchanged"
    assert response["status"] == "revised"
    assert response["changes"] == []
    assert response["revised"]["ingredients"] == [
        {"name": row["name"], "amount": row["amount"]} for row in source["ingredients"]
    ]
    assert value["model_calls"] == []


def test_every_stored_service_response_matches_the_complete_production_shape():
    _, observations, _ = validate_fixture_bundle()
    responses = [
        observation.execution.final_service_response
        for observation in observations
        if observation.execution.final_service_response is not None
    ]
    assert len(responses) == 5
    validated = [ReviseResponse.model_validate(response) for response in responses]
    assert {response.status for response in validated} == {"revised", "refused", "failed"}


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


def test_cost_provenance_requires_price_inputs_only_for_estimates():
    measured = Cost.model_validate(
        {
            "applicability": "value",
            "value": 0.25,
            "provenance": "measured",
            "price_inputs": None,
        }
    )
    estimated = Cost.model_validate(
        {
            "applicability": "value",
            "value": 0.1,
            "provenance": "estimated",
            "price_inputs": {"input_per_million_usd": 0.2},
        }
    )
    assert measured.provenance == "measured"
    assert estimated.price_inputs == {"input_per_million_usd": 0.2}
    with pytest.raises(ValidationError, match="estimated cost requires price inputs"):
        Cost.model_validate(
            {
                "applicability": "value",
                "value": 0.1,
                "provenance": "estimated",
                "price_inputs": None,
            }
        )


def test_frozen_contract_can_represent_required_provenance_and_aggregates():
    metadata, _, summary = validate_fixture_bundle()
    resumed = next(unit for unit in metadata.plan if unit.case_id == "resumed")
    assert metadata.code_identity.commit and metadata.code_identity.tree
    assert metadata.identities.prompt_sha256 != metadata.identities.response_schema_sha256
    assert resumed.cumulative_telemetry is not None
    assert resumed.cumulative_telemetry.http_attempts == 2

    assert summary.initial_failure_codes == {"unexplained_change": 2}
    assert summary.final_failure_codes == {"unexplained_change": 1}
    assert summary.latency.revision_s.sample_count == 8
    assert len(summary.cases) == 8
    assert all(case.all_planned_completed for case in summary.cases)
    assert summary.semantic_success.applicability == "not_applicable"
    assert summary.semantic_success.definition is None
    assert summary.totals.reasks == 2
    assert summary.totals.http_429_responses == 1
    assert summary.totals.http_429_retries == 1


def test_reference_validity_is_aggregated_independently_from_structure():
    observations = fixture_observations()
    finding = next(
        finding
        for value in observations.values()
        for finding in value["deterministic_evaluation"]["answers"]
        if finding["structure_valid"] is True and finding["reference_valid"] is True
    )
    finding["reference_valid"] = False

    summary = fixture_summary(observations)

    assert summary["structural_validity"]["numerator"] == (
        summary["reference_validity"]["numerator"] + 1
    )


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


def test_api_error_fixture_is_a_transport_failure_without_an_http_response():
    value = read_json(fixture_root() / "observations/api-error__r01/attempt-001.json")
    attempt = value["model_calls"][0]["http_attempts"][0]
    assert value["execution"]["terminal_outcome"] == "api_error"
    assert value["execution"]["outcome_source"] == "transport"
    assert attempt["state"] == "transport_error"
    assert attempt["delivery"] == "failed"
    assert attempt["status_code"] is None
    assert attempt["safe_response_text"] is None
    assert value["telemetry"]["provider_round_trip_s"] == {
        "applicability": "value",
        "value": 0.25,
    }


def test_partial_http_usage_remains_unknown_in_attempt_totals():
    partial = read_json(
        fixture_root() / "observations/revised-after-reask-429__r01/attempt-001.json"
    )
    complete = read_json(
        fixture_root() / "observations/check-failed__r01/attempt-001.json"
    )
    assert partial["model_calls"][0]["http_attempts"][0]["usage"] is None
    assert partial["telemetry"]["tokens"] == {
        "input_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
        "cached_tokens": None,
    }
    assert complete["telemetry"]["tokens"] == {
        "input_tokens": 20,
        "output_tokens": 40,
        "reasoning_tokens": 0,
        "cached_tokens": 0,
    }


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


def test_terminal_429_is_a_response_without_an_actual_retry():
    value = read_json(
        fixture_root() / "observations/revised-after-reask-429__r01/attempt-001.json"
    )
    value["model_calls"][0]["http_attempts"] = value["model_calls"][0][
        "http_attempts"
    ][:1]
    value["telemetry"].update(
        http_attempts=2,
        http_429_responses=1,
        http_429_retries=0,
    )
    Observation.model_validate(value)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda value: value["input"]["availability"].pop(),
            "availability must align",
        ),
        (
            lambda value: value["model_calls"][1].update(index=1),
            "logical calls must be one-based and contiguous",
        ),
        (
            lambda value: value["telemetry"].update(reasks=99),
            "re-ask telemetry does not match",
        ),
        (
            lambda value: value["telemetry"].update(http_429_responses=0),
            "HTTP 429 response telemetry does not match",
        ),
        (
            lambda value: value["telemetry"].update(http_429_retries=0),
            "HTTP 429 retry telemetry does not match",
        ),
    ],
)
def test_observation_rejects_cross_field_count_mismatches(mutate, message):
    value = read_json(
        fixture_root() / "observations/revised-after-reask-429__r01/attempt-001.json"
    )
    mutate(value)
    with pytest.raises(ValidationError, match=message):
        Observation.model_validate(value)


def test_fixture_only_consumer_can_find_judge_source_fields_without_runner_imports():
    # Deliberately use dictionaries here: the Judge contract is JSON, not Python models.
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
