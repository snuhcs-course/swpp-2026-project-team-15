# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Offline observation integration checks preserving production evidence and outcomes."""

import json
from copy import deepcopy

import pytest
from experiments.revision_evaluation.contract import Observation
from experiments.revision_evaluation.evaluation import evaluate_observation
from experiments.revision_evaluation.generate_contract import fixture_observations


def observation(case):
    """Read a deterministic v1 observation without executing a model or production check."""
    return Observation.model_validate(fixture_observations()[f"{case}__r01/attempt-001.json"])


@pytest.mark.parametrize("value", list(fixture_observations().values()))
def test_evaluation_preserves_all_source_and_production_fields(value):
    source = Observation.model_validate(value)
    before = source.model_dump()
    evaluated = evaluate_observation(source)
    assert (
        source.deterministic_evaluation.deleted_ingredient_explanation
        == evaluated.deterministic_evaluation.deleted_ingredient_explanation
    )
    assert source.model_dump() == before
    assert evaluated is not source
    after = evaluated.model_dump()
    # Only measured parsing and deterministic annotations may change.
    after.pop("deterministic_evaluation")
    before.pop("deterministic_evaluation")
    for left, right in zip(after["model_calls"], before["model_calls"], strict=True):
        left.pop("parsing")
        right.pop("parsing")
    assert after == before


@pytest.mark.parametrize(
    "case,parsed,structure",
    [
        ("response-error-json", False, None),
        ("response-error-structure", True, False),
    ],
)
def test_response_errors_keep_raw_content_and_their_separate_parse_and_shape_results(
    case,
    parsed,
    structure,
):
    source = observation(case)
    result = evaluate_observation(source)
    assert result.execution.terminal_outcome == "response_error"
    assert result.model_calls[0].parsing.succeeded is parsed
    assert result.deterministic_evaluation.answers[0].structure_valid is structure
    assert result.model_calls[0].decoded_answer == source.model_calls[0].decoded_answer
    assert result.model_calls[0].http_attempts == source.model_calls[0].http_attempts


def test_structure_and_reference_findings_are_independent_of_production_acceptance():
    source = observation("revised-after-reask-429")
    final = source.model_calls[-1]
    answer = deepcopy(final.decoded_answer)
    answer["changes"][0]["ingredient_refs"] = [999]
    final.http_attempts[-1].safe_response_text = json.dumps(answer)
    before_execution, before_checks = source.execution.model_dump(), deepcopy(source.checks)
    result = evaluate_observation(source)
    finding = result.deterministic_evaluation.answers[-1]
    assert finding.structure_valid is True and finding.reference_valid is False
    assert finding.issues
    assert result.execution.model_dump() == before_execution and result.checks == before_checks


def test_coverage_uses_terminal_answer_not_the_earlier_rejected_answer():
    source = observation("revised-after-reask-429")
    initial, final = source.model_calls
    initial.decoded_answer["changes"] = deepcopy(final.decoded_answer["changes"])
    final.decoded_answer["changes"] = []
    result = evaluate_observation(source)
    coverage = result.deterministic_evaluation.deleted_ingredient_explanation
    assert (coverage.numerator, coverage.denominator, coverage.value) == (0, 1, 0)
    assert result.execution.terminal_outcome == "revised"


def test_failed_terminal_answer_does_not_fall_back_to_initial_coverage():
    source = observation("revised-after-reask-429")
    source.model_calls[-1].decoded_answer = None
    source.model_calls[-1].http_attempts[-1].safe_response_text = "{"
    result = evaluate_observation(source)
    assert result.deterministic_evaluation.answers[-1].structure_valid is None
    assert result.deterministic_evaluation.deleted_ingredient_explanation.value is None


def test_coverage_for_check_failed_answer_remains_available():
    result = evaluate_observation(observation("check-failed"))
    coverage = result.deterministic_evaluation.deleted_ingredient_explanation
    assert (coverage.numerator, coverage.denominator) == (0, 1)
    assert result.execution.terminal_outcome == "check_failed"


def test_no_call_and_api_error_paths_do_not_receive_fabricated_parsing():
    no_call = evaluate_observation(observation("unchanged"))
    api_error = evaluate_observation(observation("api-error"))
    assert no_call.deterministic_evaluation.answers == []
    assert api_error.model_calls[0].parsing.attempted is False
    finding = api_error.deterministic_evaluation.answers[0]
    assert finding.structure_valid is finding.reference_valid is None


def test_ambiguous_multiple_assistant_texts_are_rejected_instead_of_discarded():
    source = observation("revised-after-reask-429")
    first = source.model_calls[0].http_attempts[0]
    first.status_code = 200
    first.safe_response_text = "{}"
    source.telemetry.http_429_responses = source.telemetry.http_429_retries = 0
    with pytest.raises(ValueError, match="multiple assistant"):
        evaluate_observation(source)


def test_incomplete_attempt_does_not_receive_terminal_coverage_from_a_parsed_answer():
    source = observation("revised-after-reask-429")
    source.execution.state = "interrupted"
    source.execution.terminal_outcome = source.execution.outcome_source = None
    source.execution.finished_at = None
    source.execution.checkpoint_stage = "check_completed"
    result = evaluate_observation(source)
    assert result.deterministic_evaluation.answers[-1].structure_valid is True
    assert result.deterministic_evaluation.deleted_ingredient_explanation.value is None
    assert result.execution.state == "interrupted"


def test_offline_re_evaluation_is_deterministic():
    first = evaluate_observation(observation("revised-after-reask-429"))
    assert evaluate_observation(first).model_dump(by_alias=True) == first.model_dump(by_alias=True)
