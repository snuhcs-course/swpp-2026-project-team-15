# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Phone recheck leftovers (research/experiments/recheck_leftovers)."""

from app.dishes.catalog import Catalog
from app.dishes.recipe_names import RecipeNames

NAMES = RecipeNames.load()
CATALOG = Catalog.load(names=NAMES)


def test_jjajang_ramen_needs_the_jjajang_ramen_product_not_any_ramen():
    # The model never named 짜장라면 for 라면·양파·돼지고기 (3/3) and did for 짜파게티 (2/2): the
    # dish is cooked from the jjajang ramen product, which the dish list now says.
    dish = CATALOG.get("jjapaghetti-egg")
    assert "짜장라면" in dish.key_ingredients and "라면" not in dish.key_ingredients
    assert CATALOG.uses(dish, "짜파게티")
    assert not CATALOG.uses(dish, "라면") and CATALOG.uses(dish, "양파")
    # Owning the product covers the recipe's general 라면 row and its sauce packet.
    owned = NAMES.owned(["짜파게티"])
    assert NAMES.status("라면", owned) == "owned"
    assert NAMES.status("짜파게티 스프", owned) == "owned"


def test_sea_salt_and_white_pepper_are_the_staples():
    assert NAMES.status("천일염", NAMES.owned(["두부"])) == "assumed"
    assert NAMES.status("백후추", NAMES.owned(["두부"])) == "assumed"


def test_vinegar_is_not_assumed_but_owned_when_picked():
    # 식초 is an onboarding choice, not a staple: "없음" unless the user picked it (the recheck
    # fridge had 설탕·양파·대파·두부·감자 only).
    assert NAMES.status("식초", NAMES.owned(["두부"])) == "unavailable"
    assert NAMES.status("식초", NAMES.owned(["식초"])) == "owned"
