# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Offline tests of round 2 of the revision study and of the candidate rules it compares."""

import json
from pathlib import Path

import pytest
from experiments.dish_revision import round2, run_round2

from app.dishes.catalog import Catalog
from app.dishes.recipes import RecipeStore
from app.dishes.revision import Reviser
from app.dishes.revision_check import identity_missing, mentions

HERE = Path(run_round2.__file__).parent
CATALOG = Catalog.load()
STORE = RecipeStore.load(HERE / "fixtures.json")


@pytest.mark.parametrize(
    ("text", "name", "expected"),
    [
        ("밥을 넣고 볶는다", "밥", True),
        ("파, 마늘을 썬다", "파", True),
        ("김을 부순다", "김", True),
        ("밥솥에 쌀을 안친다", "밥", False),
        ("김치를 썬다", "김", False),
        ("대파를 썬다", "파", False),
        ("파프리카를 썬다", "파", False),
        ("김치를 잘게 썬다", "김치", True),
    ],
)
def test_one_character_names_match_as_words_only(text, name, expected):
    assert mentions(text, name) is expected


def _status(dish_id: str, ingredients: list[str]) -> list[str]:
    return Reviser(CATALOG, CATALOG, None, STORE).availability(STORE.get(dish_id), ingredients)


def test_identity_missing_uses_the_end_of_the_dish_name_for_one_character_names():
    recipe = STORE.get("kimchi-fried-rice")
    no_rice = _status("kimchi-fried-rice", ["김치", "계란", "대파"])
    assert identity_missing("김치볶음밥", recipe, no_rice) == ["밥"]
    no_kimchi = _status("kimchi-fried-rice", ["밥", "계란", "대파"])
    assert identity_missing("김치볶음밥", recipe, no_kimchi) == ["김치"]
    no_onion = _status("kimchi-fried-rice", ["밥", "김치", "계란"])
    assert identity_missing("김치볶음밥", recipe, no_onion) == []


def _answer(recipe, drop: set[str], changes=None, add=()):
    rows = [
        {"name": r.name, "amount": r.amount or ""} for r in recipe.ingredients if r.name not in drop
    ]
    rows += [{"name": n, "amount": ""} for n in add]
    return {
        "can_revise": True,
        "refusal_reason": "",
        "servings": 0,
        "ingredients": rows,
        "steps": ["재료를 볶는다.", "그릇에 담는다."],
        "tips": [],
        "changes": changes or [],
    }


def _row(recipe, name: str) -> int:
    return next(i for i, r in enumerate(recipe.ingredients, 1) if r.name == name)


def test_dropping_an_unavailable_main_ingredient_is_a_refusal_only_in_the_strict_variants():
    recipe = STORE.get("kimchi-fried-rice")
    owned = ["김치", "계란", "대파"]
    status = _status("kimchi-fried-rice", owned)
    raw = _answer(
        recipe,
        {"밥"},
        [
            {
                "kind": "omission",
                "reason": "밥이 없어 뺐어요",
                "ingredient_refs": [_row(recipe, "밥")],
                "step_refs": [],
            }
        ],
    )
    args = (raw, recipe, "김치볶음밥", status, CATALOG, owned)
    assert round2.decide("current", *args)["status"] == "revised"
    assert round2.decide("main-kept", *args) == {
        "status": "refused",
        "code": "refuse_needed",
        "call": True,
    }
    assert round2.decide("prescreen", *args) == {
        "status": "refused",
        "code": "prescreen",
        "call": False,
    }


def test_a_main_ingredient_replaced_by_an_owned_one_in_a_named_change_is_accepted():
    recipe = STORE.get("kimchi-fried-rice")
    owned = ["밥", "계란", "대파", "깍두기"]
    status = _status("kimchi-fried-rice", owned)
    change = [
        {
            "kind": "substitution",
            "reason": "김치 대신 깍두기",
            "ingredient_refs": [_row(recipe, "김치")],
            "step_refs": [],
        }
    ]
    raw = _answer(recipe, {"김치"}, change, add=("깍두기",))
    assert (
        round2.decide("main-kept", raw, recipe, "김치볶음밥", status, CATALOG, owned)["status"]
        == "revised"
    )


def test_summary_counts_and_transitions():
    rows = [
        {"id": "a", "expect": "refuse", "status": "revised", "code": None, "call": True},
        {"id": "b", "expect": "revise", "status": "refused", "code": "prescreen", "call": False},
    ]
    s = round2.summarize(rows)
    assert s["wrong_accepted"] == 1 and s["wrongful_refusals"] == 1 and s["model_calls"] == 1
    after = [dict(rows[0], status="refused", code="refuse_needed"), rows[1]]
    assert round2.transitions(rows, after) == [
        {"id": "a", "expect": "refuse", "from": "revised", "to": "refused", "code": "refuse_needed"}
    ]


def test_real_case_builder_labels_by_role():
    store = RecipeStore.load(HERE / "fixtures.json")
    recipes = {d: store.get(d) for d in json.loads((HERE / "fixtures.json").read_text())["recipes"]}
    cases = round2.build_real_cases(recipes, CATALOG)
    assert cases and all(c["expect"] in {"refuse", "revise"} for c in cases)
    for case in cases:
        recipe = recipes[case["dish_id"]]
        gone = [r for r in recipe.ingredients if r.name not in case["ingredients"]]
        assert gone and (case["expect"] == "refuse") == any(r.role == "main" for r in gone)


def test_dry_run_makes_no_call(capsys):
    assert run_round2.main([]) == 0
    assert "dry run" in capsys.readouterr().out
