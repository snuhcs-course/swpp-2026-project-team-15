# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Offline parse classification and denominator checks using the frozen contract."""

import json

import pytest
from experiments.revision_evaluation.contract import fixture_root, validate_fixture_bundle
from experiments.revision_evaluation.parsing import (
    aggregate_json_parse_success,
    classify_json_response,
)


@pytest.mark.parametrize("text", ['{"can_revise": true}', "[]", "{}", "null", "false", '"밥"', "7"])
def test_valid_json_is_parse_success_independent_of_revision_structure(text):
    assert classify_json_response(text).model_dump() == {
        "attempted": True,
        "succeeded": True,
        "error": None,
    }


@pytest.mark.parametrize("text", ["", " ", "{", '{"private": secret-value}', "```json\n{}\n```"])
def test_malformed_or_empty_returned_text_is_a_parse_failure(text):
    assert classify_json_response(text).model_dump() == {
        "attempted": True,
        "succeeded": False,
        "error": "invalid JSON",
    }


def test_no_response_is_not_a_parse_attempt():
    assert classify_json_response(None).model_dump() == {
        "attempted": False,
        "succeeded": None,
        "error": None,
    }


@pytest.mark.parametrize("texts", [[], [None], [None, None]])
def test_no_call_or_transport_only_sequences_have_no_parse_denominator(texts):
    assert aggregate_json_parse_success(iter(texts)).model_dump() == {
        "numerator": 0,
        "denominator": 0,
        "value": None,
    }


def test_initial_and_reask_texts_both_count_without_including_no_responses():
    texts = [None, "{", "[]", None, '{"can_revise": true}', ""]
    assert aggregate_json_parse_success(iter(texts)).model_dump() == {
        "numerator": 2,
        "denominator": 4,
        "value": 0.5,
    }
    assert texts == [None, "{", "[]", None, '{"can_revise": true}', ""]


def test_frozen_responses_reproduce_published_parse_summary():
    _, observations, summary = validate_fixture_bundle()
    texts = [
        attempt.safe_response_text
        for observation in observations
        for call in observation.model_calls
        for attempt in call.http_attempts
    ]
    assert aggregate_json_parse_success(texts) == summary.json_parse_success
    # The fixture's parsed array must stay in the parse-success numerator even
    # though the production model rejects its top-level response structure.
    raw = json.loads(
        (fixture_root() / "observations/response-error-structure__r01/attempt-001.json").read_text(
            encoding="utf-8"
        )
    )
    assert raw["execution"]["terminal_outcome"] == "response_error"
    assert (
        classify_json_response(
            raw["model_calls"][0]["http_attempts"][0]["safe_response_text"]
        ).succeeded
        is True
    )
