# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""Known-answer tests for the independent checkers: hand-built recipes with planted violations."""

from experiments.revision_input import checkers as ck

from recipe_revision.models import SourceIngredient, SourceRecipe, SourceStep

MAIN, SECONDARY, SEASONING = "3060001", "3060002", "3060003"


def ingredient(row_id, ingredient_id, name, type_code, original=None):
    return SourceIngredient(row_id, ingredient_id, name, "1", type_code, None, original or name)


def recipe(name="계란말이", ingredients=None, steps=None):
    ingredients = ingredients or [
        ingredient(1, 32, "계란", MAIN),
        ingredient(2, 99, "대파", SECONDARY),
        ingredient(3, 284, "소금", SEASONING),
        ingredient(4, 554, "후추", SEASONING),
    ]
    steps = steps or [SourceStep(10, 1, "계란을 풀고 대파를 썰어 넣어 익힌다.", None)]
    return SourceRecipe(
        1, name, None, None, None, None, None, "1인분", None, tuple(ingredients), tuple(steps)
    )


NAMES = {32: "계란", 99: "대파", 284: "소금", 554: "후추", 345: "양파"}


def result(ids, steps=("계란을 풀어 익힌다.",), changes=(), can_revise=True):
    return {
        "can_revise": can_revise,
        "reason": "",
        "changes": list(changes),
        "revised_recipe": {
            "name": "계란말이",
            "servings": "1인분",
            "ingredients": [
                {"ingredient_id": i, "name": NAMES[i], "quantity_text": "1"} for i in ids
            ],
            "steps": [
                {"step_number": n, "instruction": s, "tip": None} for n, s in enumerate(steps, 1)
            ],
        },
    }


def test_allowed_ids_by_policy():
    r = recipe()
    assert ck.allowed_ids(r, [32], "strict") == {32, ck.WATER_ID}
    assert ck.allowed_ids(r, [32], "staples") == {32, 284, 554, ck.WATER_ID}
    # list: only the assumed seasonings that the recipe contains
    assert ck.allowed_ids(r, [32], "list", {284, 999}) == {32, 284, ck.WATER_ID}
    assert ck.allowed_ids(r, [32], "list") == {32, ck.WATER_ID}


def test_expected_verdict_refuse_ambiguous_revise():
    r = recipe()
    assert ck.expected_verdict(r, {99, 284, 554})[0] == "refuse"  # dish-name ingredient missing
    assert ck.expected_verdict(r, {32, 284, 554})[0] == "revise"  # only a secondary one missing
    only_main = recipe(
        name="볶음",
        ingredients=[ingredient(1, 32, "계란", MAIN), ingredient(2, 99, "대파", SECONDARY)],
    )
    assert ck.expected_verdict(only_main, {99})[0] == "ambiguous"
    assert ck.expected_verdict(r, {32, 99, 284, 554})[0] == "revise"  # nothing missing


def test_id_level_flags_unavailable_and_unknown_ids():
    allowed = {32, 284, ck.WATER_ID}
    clean = ck.id_level(result([32, 284]), allowed, NAMES)
    assert clean["violating_ids"] == [] and clean["unknown_ids"] == []
    bad = ck.id_level(result([32, 99]), allowed, NAMES)
    assert bad["violating_ids"] == [99]
    unknown = result([32])
    unknown["revised_recipe"]["ingredients"].append(
        {"ingredient_id": 7777, "name": "?", "quantity_text": None}
    )
    assert ck.id_level(unknown, allowed, NAMES)["unknown_ids"] == [7777]
    assert ck.id_level(result([], can_revise=False), allowed, NAMES) == {"applicable": False}


def test_step_level_separates_stale_from_novel_mentions():
    r = recipe()
    index = ck.NameIndex(NAMES, {1: r})
    allowed = {32, 284, 554, ck.WATER_ID}  # 대파 is unavailable
    stale = result([32], steps=("계란을 풀고 대파를 넣는다.",))
    assert ck.step_level(stale, r, allowed, index)["stale_missing_terms"] == ["대파"]
    novel = result([32], steps=("계란을 풀고 양파를 넣는다.",))
    assert ck.step_level(novel, r, allowed, index)["novel_terms"] == ["양파"]
    clean = result([32], steps=("계란을 풀어 익힌다.",))
    out = ck.step_level(clean, r, allowed, index)
    assert out["stale_missing_terms"] == [] and out["novel_terms"] == []


def test_structure_reports_planted_inconsistencies():
    r = recipe()
    declared = [
        {
            "kind": "omission",
            "reason": "x",
            "source_ingredient_row_ids": [2],
            "source_step_ids": [],
        }
    ]
    ok = result([32, 284, 554], changes=declared)
    assert "undeclared_removal" not in ck.structure(ok, r)["issues"]
    undeclared = result([32, 284, 554])
    assert "undeclared_removal" in ck.structure(undeclared, r)["issues"]
    added = result([32, 99, 284, 554, 345], changes=declared)
    assert "addition_without_substitution" in ck.structure(added, r)["issues"]
    bad_numbers = result([32, 99, 284, 554], steps=("a", "b"))
    bad_numbers["revised_recipe"]["steps"][1]["step_number"] = 5
    assert "step_numbers_not_sequential" in ck.structure(bad_numbers, r)["issues"]
    dangling = result(
        [32, 99, 284, 554],
        changes=[
            {
                "kind": "quantity",
                "reason": "x",
                "source_ingredient_row_ids": [404],
                "source_step_ids": [],
            }
        ],
    )
    assert "invalid_reference" in ck.structure(dangling, r)["issues"]


def test_safety_requires_heat_steps_when_raw_risk_remains():
    meat = recipe(
        name="닭볶음",
        ingredients=[ingredient(1, 32, "닭고기", MAIN)],
        steps=[SourceStep(10, 1, "닭고기를 속까지 완전히 익힌다.", None)],
    )
    names = {32: "닭고기"}
    kept = result([32], steps=("닭고기를 속까지 완전히 익힌다.",))
    kept["revised_recipe"]["ingredients"][0]["name"] = "닭고기"
    assert ck.safety(kept, meat, names)["retained"] is True
    raw_step = result([32], steps=("닭고기를 접시에 담는다.",))
    assert ck.safety(raw_step, meat, names)["retained"] is False
    no_risk = recipe(name="파전", ingredients=[ingredient(1, 99, "대파", SECONDARY)])
    assert ck.safety(result([99]), no_risk, NAMES) == {"applicable": False}
