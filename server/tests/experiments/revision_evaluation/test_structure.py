# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Offline structure checks grounded in the served response schema and prompt."""

import json
from copy import deepcopy

import pytest
from experiments.revision_evaluation.structure import (
    aggregate_structural_validity,
    evaluate_structure,
)

from tests.dishes.test_revision import GOOD


def refusal():
    """Return the empty-list refusal shape specified by the current prompt."""
    return {
        "can_revise": False,
        "refusal_reason": "핵심 재료가 없어요.",
        "servings": 0,
        "ingredients": [],
        "steps": [],
        "tips": [],
        "changes": [],
    }


@pytest.mark.parametrize("answer", [GOOD, refusal()])
def test_valid_revision_and_refusal_pass_without_mutating_input(answer):
    before = deepcopy(answer)
    result = evaluate_structure(answer)
    assert result.valid is True and result.issues == ()
    assert answer == before


@pytest.mark.parametrize("answer", [[], None, True, 7, "answer"])
def test_parsed_non_object_values_are_structural_failures(answer):
    assert evaluate_structure(answer).issues == ("$: expected object",)


@pytest.mark.parametrize("field", list(GOOD))
def test_every_required_field_is_checked(field):
    answer = deepcopy(GOOD)
    del answer[field]
    result = evaluate_structure(answer)
    assert result.valid is False
    assert f"$.{field}: required field missing" in result.issues


@pytest.mark.parametrize(
    "patch",
    [
        {"can_revise": 1},
        {"refusal_reason": None},
        {"servings": True},
        {"servings": "2"},
        {"ingredients": {}},
        {"steps": [1]},
        {"tips": [None]},
        {"changes": [False]},
        {"ingredients": [{"name": "밥"}]},
        {"ingredients": [{"name": "밥", "amount": None}]},
        {
            "changes": [
                {"kind": "omission", "reason": "x", "ingredient_refs": [True], "step_refs": []}
            ]
        },
    ],
)
def test_wrong_field_and_nested_types_fail_without_coercion(patch):
    answer = {**deepcopy(GOOD), **patch}
    before = deepcopy(answer)
    assert evaluate_structure(answer).valid is False
    assert answer == before


@pytest.mark.parametrize(
    "patch", [{"refusal_reason": "cannot revise"}, {"ingredients": []}, {"steps": []}]
)
def test_feasible_answer_requires_recipe_and_no_refusal_reason(patch):
    assert evaluate_structure({**deepcopy(GOOD), **patch}).valid is False


@pytest.mark.parametrize("field", ["ingredients", "steps", "tips", "changes"])
def test_refusal_requires_empty_lists(field):
    answer = refusal()
    answer[field] = deepcopy(GOOD[field]) if GOOD[field] else ["tip"]
    assert evaluate_structure(answer).valid is False


@pytest.mark.parametrize("reason", ["", "  "])
def test_refusal_requires_a_specific_reason(reason):
    answer = refusal()
    answer["refusal_reason"] = reason
    assert evaluate_structure(answer).valid is False


def test_additional_fields_fail_without_echoing_untrusted_keys():
    answer = {**deepcopy(GOOD), "private-response-value": "secret"}
    result = evaluate_structure(answer)
    assert result.valid is False and "$: unexpected fields" in result.issues
    assert "private-response-value" not in repr(result.issues)
    assert "secret" not in repr(result.issues)


def test_structural_validity_has_its_own_parsed_response_denominator():
    texts = [None, "{", "[]", "null", json.dumps(GOOD), json.dumps(refusal()), "{}"]
    assert aggregate_structural_validity(iter(texts)).model_dump() == {
        "numerator": 2,
        "denominator": 5,
        "value": 0.4,
    }


def test_no_parsed_responses_have_no_structural_rate():
    assert aggregate_structural_validity([None, "", "{"]).model_dump() == {
        "numerator": 0,
        "denominator": 0,
        "value": None,
    }


def test_change_kind_and_reference_bounds_do_not_change_the_structural_metric():
    answer = deepcopy(GOOD)
    answer["changes"][0].update(kind="unknown", ingredient_refs=[-1, 999], step_refs=[0])
    # Those are correctly typed but invalid references/kinds. Task 3.3 evaluates
    # them independently, so this test prevents mixing the two validity metrics.
    assert evaluate_structure(answer).valid is True
