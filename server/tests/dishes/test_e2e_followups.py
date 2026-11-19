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
