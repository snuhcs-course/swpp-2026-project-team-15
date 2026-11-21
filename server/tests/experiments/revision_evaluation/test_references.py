# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Offline change-kind and original-source reference boundary tests."""

from copy import deepcopy

import pytest
from experiments.revision_evaluation.references import evaluate_references
from experiments.revision_evaluation.structure import evaluate_structure

from tests.dishes.test_revision import GOOD, RECIPE

INGREDIENT_COUNT = len(RECIPE["ingredients"])
STEP_COUNT = len(RECIPE["steps"])


def evaluate(answer, ingredient_count=INGREDIENT_COUNT, step_count=STEP_COUNT):
    """Use the existing source fixture's counts rather than its revised answer size."""
    return evaluate_references(answer, ingredient_count=ingredient_count, step_count=step_count)


@pytest.mark.parametrize("kind", ["omission", "substitution", "quantity", "servings", "step"])
def test_all_defined_kinds_accept_source_range_endpoints_without_mutation(kind):
    answer = deepcopy(GOOD)
    answer["changes"][0].update(kind=kind, ingredient_refs=[1, 5], step_refs=[1, 3])
    before = deepcopy(answer)
    result = evaluate(answer)
    assert result.valid is True and result.issues == ()
    assert answer == before


@pytest.mark.parametrize("field", ["ingredient_refs", "step_refs"])
@pytest.mark.parametrize("ref", [0, -1, 999, True, False, "1", 1.0, None])
def test_invalid_reference_bounds_and_types_fail_without_modifying_answer(field, ref):
    answer = deepcopy(GOOD)
    answer["changes"][0][field] = [ref]
    before = deepcopy(answer)
    result = evaluate(answer)
    assert result.valid is False and any(field in issue for issue in result.issues)
    assert answer == before


@pytest.mark.parametrize("field,first_invalid", [("ingredient_refs", 6), ("step_refs", 4)])
def test_first_position_past_the_source_end_is_invalid(field, first_invalid):
    answer = deepcopy(GOOD)
    answer["changes"][0][field] = [first_invalid]
    assert evaluate(answer).valid is False


@pytest.mark.parametrize("kind", ["swap", "", None, 1, [], {}])
def test_unknown_or_malformed_kinds_fail(kind):
    answer = deepcopy(GOOD)
    answer["changes"][0]["kind"] = kind
    assert evaluate(answer).valid is False


@pytest.mark.parametrize("field", ["ingredient_refs", "step_refs"])
@pytest.mark.parametrize("refs", [None, 1, "1", {}])
def test_malformed_reference_containers_fail(field, refs):
    answer = deepcopy(GOOD)
    answer["changes"][0][field] = refs
    assert evaluate(answer).valid is False


def test_empty_and_duplicate_refs_are_preserved():
    answer = {"changes": [{"kind": "step", "ingredient_refs": [], "step_refs": [1, 1]}]}
    before = deepcopy(answer)
    assert evaluate(answer).valid is True
    assert answer == before


def test_no_changes_have_no_invalid_references_even_with_empty_source():
    assert evaluate({"changes": []}, ingredient_count=0, step_count=0).valid is True
    change = {"kind": "step", "ingredient_refs": [], "step_refs": []}
    assert evaluate({"changes": [change]}, ingredient_count=0, step_count=0).valid is True
    change["step_refs"] = [1]
    assert evaluate({"changes": [change]}, ingredient_count=0, step_count=0).valid is False


@pytest.mark.parametrize("answer", [None, [], {}, {"changes": None}, {"changes": [None]}])
def test_malformed_parsed_answers_report_findings_instead_of_crashing(answer):
    assert evaluate(answer).valid is False


@pytest.mark.parametrize("counts", [(True, 1), (-1, 1), (1, -1), (1, 1.0)])
def test_invalid_source_counts_raise_instead_of_misclassifying_model_output(counts):
    with pytest.raises(ValueError, match="source counts"):
        evaluate({"changes": []}, ingredient_count=counts[0], step_count=counts[1])


def test_reference_validity_is_independent_of_structure_and_uses_source_dimensions():
    answer = deepcopy(GOOD)
    # The original recipe has five ingredients and three steps, while the revised
    # recipe has three ingredients and two steps; source endpoints remain valid.
    answer["changes"][0].update(ingredient_refs=[5], step_refs=[3])
    assert evaluate(answer).valid is True
    answer["changes"][0]["ingredient_refs"] = [6]
    assert evaluate_structure(answer).valid is True
    assert evaluate(answer).valid is False
