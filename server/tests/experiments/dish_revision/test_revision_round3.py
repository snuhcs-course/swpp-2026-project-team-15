# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
import pytest
from experiments.dish_revision import run_round3

from app.dishes import prompts
from app.dishes.catalog import Catalog
from app.dishes.recipes import RecipeStore


def test_reference_variant_adds_the_rule_once_after_rule_3():
    text = run_round3.reference_variant(run_round3.SERVED)
    assert text.count(run_round3.REFERENCE_RULE.strip()) == 1
    assert run_round3.REFERENCE_RULE.strip() not in run_round3.SERVED
    assert run_round3.SERVED == prompts.REVISE_SYSTEM


def test_reference_variant_refuses_an_unknown_prompt():
    with pytest.raises(ValueError):
        run_round3.reference_variant("no anchor here")


def test_card_cases_use_the_dish_key_ingredients_for_dishes_with_a_recipe():
    catalog = Catalog.load()
    dish = catalog.all()[0]
    recipe = {
        "dish_id": dish.id,
        "ingredients": [{"name": "꽃소금", "role": "seasoning"}],
        "steps": [{"n": 1, "text": "간을 한다"}],
    }
    store = RecipeStore({dish.id: _recipe(recipe)})
    cases = run_round3.card_cases(catalog, store)
    assert cases == [{"dish_id": dish.id, "ingredients": list(dish.key_ingredients)}]


def _recipe(raw):
    from app.dishes.schemas import SourceRecipe

    return SourceRecipe.model_validate(raw)


def test_in_range_refs_drops_only_references_outside_the_source():
    data = {
        "changes": [
            {"kind": "omission", "reason": "r", "ingredient_refs": [0, 2, 9], "step_refs": [1, 4]}
        ]
    }
    out = run_round3.in_range_refs(data, n_rows=3, n_steps=3)
    assert out["changes"] == [
        {"kind": "omission", "reason": "r", "ingredient_refs": [2], "step_refs": [1]}
    ]
    assert data["changes"][0]["ingredient_refs"] == [0, 2, 9]  # input untouched
