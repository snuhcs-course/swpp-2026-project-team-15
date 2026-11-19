# AI-generated with Claude Code (Opus 5.5), 2026-11-19; not yet reviewed.
"""Phone test follow-ups (research/experiments/e2e_followups)."""

from app.dishes.catalog import Catalog
from app.dishes.recipe_names import RecipeNames

NAMES = RecipeNames.load()
CATALOG = Catalog.load(names=NAMES)


def test_a_seasoning_in_the_fridge_is_owned_not_assumed():
    assert NAMES.status("소금", NAMES.owned(["소금"])) == "owned"
    assert NAMES.status("소금", NAMES.owned(["두부"])) == "assumed"
    assert NAMES.status("꽃소금", NAMES.owned(["소금"])) == "owned"


def test_pantry_seasonings_do_not_make_unrelated_fridges_use_dishes():
    # The staples (staples.json) are assumed at home; 고추장 or 된장 are real key ingredients.
    fridge = ["초콜릿", "소금", "간장", "참기름", "설탕", "고춧가루", "다진마늘"]
    used = [d.name for d in CATALOG.all() if any(CATALOG.uses(d, i) for i in fridge)]
    assert used == []


def test_a_bad_reference_names_the_change_the_numbers_and_the_ranges():
    # 카레라이스 (phone test): a change pointed at ingredient row 14 of 11, twice.
    import pytest

    from app.dishes.revision_check import Violation, _checked_changes
    from app.dishes.schemas import SourceRecipe
    from tests.dishes.test_revision import RECIPE

    recipe = SourceRecipe.model_validate(RECIPE)
    raw = [
        {
            "kind": "omission",
            "reason": "밥은 가지고 있으므로 추가합니다",
            "ingredient_refs": [14],
            "step_refs": [1],
        }
    ]
    with pytest.raises(Violation) as caught:
        _checked_changes(raw, recipe)
    message = caught.value.message
    n_rows, n_steps = len(recipe.ingredients), len(recipe.steps)
    assert caught.value.code == "bad_reference"
    assert "Change 1" in message and "[14]" in message
    assert f"1..{n_rows}" in message and f"1..{n_steps}" in message
