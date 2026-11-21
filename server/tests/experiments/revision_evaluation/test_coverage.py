# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Compatibility and coverage tests for preserved source ingredient rows."""

from copy import deepcopy

import pytest
from experiments.dish_revision.scoring import dropped_ingredients, ingredient_coverage
from experiments.revision_evaluation.contract import SourceRecipeSnapshot
from experiments.revision_evaluation.coverage import deleted_ingredient_coverage

from app.dishes.schemas import SourceRecipe


def recipe(names):
    """Build a compact source fixture with row identity preserved even for duplicate names."""
    return SourceRecipe.model_validate(
        {
            "dish_id": "coverage-fixture",
            "source": "test",
            "servings": 1,
            "ingredients": [{"name": name, "amount": "", "role": "secondary"} for name in names],
            "steps": [],
            "tips": [],
        }
    )


def answer(names, refs):
    """Build a revising answer with explicit source-row references."""
    return {
        "can_revise": True,
        "ingredients": [{"name": name, "amount": ""} for name in names],
        "changes": [{"kind": "omission", "reason": "재료가 없어요.", "ingredient_refs": refs}],
    }


@pytest.mark.parametrize(
    "source,kept,expected",
    [
        (["계란", "대파"], ["달걀"], [2]),
        (["달걀", "대파"], ["계란"], [2]),
        (["참치캔", "후추"], ["참치통조림", "후춧가루"], []),
        ([" 배추 김치 "], ["김치"], []),
        (["대파"], ["다진파"], []),
        (["당근", "밥"], ["밥"], [1]),
    ],
)
def test_reused_drop_helper_matches_reviewed_name_compatibility(source, kept, expected):
    original, revised = recipe(source), answer(kept, [])
    assert dropped_ingredients(original, revised) == expected


def test_partial_explanation_counts_and_input_preservation():
    original = recipe(["계란", "당근", "대파"])
    revised = answer(["달걀"], [2])
    before_recipe, before_answer = original.model_dump(), deepcopy(revised)
    assert deleted_ingredient_coverage(original, revised).model_dump() == {
        "numerator": 1,
        "denominator": 2,
        "value": 0.5,
    }
    assert original.model_dump() == before_recipe and revised == before_answer
    assert ingredient_coverage(original, revised) == (1, 2)


@pytest.mark.parametrize(
    "refs,expected", [([], 0), ([1, 2], 2), ([1, 1], 1), ([True, "1", 1.0, 0, -1, 3], 0)]
)
def test_only_valid_references_cover_each_deleted_row_once(refs, expected):
    assert (
        deleted_ingredient_coverage(recipe(["당근", "대파"]), answer([], refs)).numerator
        == expected
    )


def test_invalid_reference_does_not_hide_a_valid_reference_in_the_same_change():
    result = deleted_ingredient_coverage(recipe(["당근", "대파"]), answer([], [1, 999]))
    assert (result.numerator, result.denominator, result.value) == (1, 2, 0.5)


def test_no_deleted_rows_are_explicitly_inapplicable():
    result = deleted_ingredient_coverage(recipe(["계란"]), answer(["달걀"], []))
    assert result.model_dump() == {"numerator": 0, "denominator": 0, "value": None}


def test_duplicate_source_names_retain_their_individual_row_identity():
    result = deleted_ingredient_coverage(recipe(["당근", "당근"]), answer([], [2]))
    assert (result.numerator, result.denominator) == (1, 2)


def test_frozen_source_snapshot_is_supported_without_losing_rows():
    source = recipe(["계란", "당근"])
    snapshot = SourceRecipeSnapshot.model_validate(
        {
            key: getattr(source, key)
            for key in ("dish_id", "source", "servings", "ingredients", "steps", "tips")
        }
        | {"ingredients": [row.model_dump() for row in source.ingredients]}
    )
    assert deleted_ingredient_coverage(snapshot, answer(["달걀"], [2])).value == 1


@pytest.mark.parametrize(
    "changes", [None, [None], [{"ingredient_refs": None}], [{"ingredient_refs": "1"}]]
)
def test_malformed_change_containers_do_not_fabricate_coverage(changes):
    revised = answer([], [])
    revised["changes"] = changes
    result = deleted_ingredient_coverage(recipe(["당근"]), revised)
    assert (result.numerator, result.denominator) == (0, 1)


@pytest.mark.parametrize(
    "revised",
    [
        None,
        {"can_revise": False},
        {"can_revise": True},
        {"can_revise": True, "ingredients": [None]},
        {"can_revise": True, "ingredients": [{"name": 1}]},
    ],
)
def test_ineligible_answers_are_not_mistaken_for_deleted_ingredient_sets(revised):
    with pytest.raises(ValueError, match="coverage requires"):
        deleted_ingredient_coverage(recipe(["당근"]), revised)
