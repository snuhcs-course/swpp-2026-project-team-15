# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
"""Offline tests of the revision study: frozen files, labelling rule, scorer and dry run."""

import json
from pathlib import Path

from experiments.dish_revision import run_revision, scoring

from app.dishes.catalog import Catalog
from app.dishes.recipes import RecipeStore
from app.dishes.revision import Reviser

HERE = Path(run_revision.__file__).parent
CATALOG = Catalog.load()


def test_frozen_cases_follow_the_labelling_rule():
    store, cases = run_revision.load()
    assert len(cases) == 36 and len(store) == 12
    assert len({c["id"] for c in cases}) == 36
    for case in cases:
        recipe = store.get(case["dish_id"])
        assert recipe is not None and CATALOG.get(case["dish_id"]) is not None
        status = Reviser(CATALOG, CATALOG, None, RecipeStore()).availability(
            recipe, case["ingredients"]
        )
        missing = [
            r.role for r, s in zip(recipe.ingredients, status, strict=True) if s == "unavailable"
        ]
        assert missing, f"{case['id']}: nothing is missing, so no model call would be made"
        assert ("main" in missing) == (case["expect"] == "refuse"), case["id"]


def test_criteria_thresholds_match_the_scorer():
    criteria = json.loads((HERE / "criteria.json").read_text(encoding="utf-8"))
    assert criteria["budget"]["model_calls_max"] == run_revision.CALL_CAP
    for metric in criteria["metrics"]:
        op, limit = scoring.THRESHOLDS[metric["id"]]
        written_op, written_limit = metric["threshold"].split()
        assert (written_op, float(written_limit)) == (op, limit)


def test_ingredient_and_step_coverage():
    recipe = RecipeStore.load(HERE / "fixtures.json").get("egg-roll")
    data = {
        "ingredients": [{"name": "달걀", "amount": ""}, {"name": "대파", "amount": ""}],
        "steps": [recipe.steps[0].text, "새로 쓴 문장"],
        "changes": [{"reason": "x", "ingredient_refs": [3], "step_refs": [2]}],
    }
    assert scoring.dropped_ingredients(recipe, data) == [3, 4, 5]  # 달걀 is kept as a synonym
    assert scoring.ingredient_coverage(recipe, data) == (1, 3)
    assert scoring.changed_steps(recipe, data) == [2, 3, 4, 5]
    assert scoring.step_coverage(recipe, data) == (1, 4)


def row(case_id, expect, status, valid=True, latency=2.0, cost=0.0005, ing=None, stp=None):
    return {
        "id": case_id,
        "expect": expect,
        "status": status,
        "valid": valid,
        "latency_s": latency,
        "cost_usd": cost,
        "ingredient_coverage": ing,
        "step_coverage": stp,
    }


def test_summary_metrics_and_verdicts():
    rows = [
        row("a", "revise", "revised", ing=(2, 2), stp=(1, 2)),
        row("b", "revise", "failed"),
        row("c", "revise", "refused"),
        row("d", "refuse", "refused"),
        row("e", "refuse", "error", valid=False, latency=None),
    ]
    m = scoring.summarize(rows)
    assert m["json_valid_rate"] == 0.8
    assert m["post_check_pass_rate"] == 0.5
    assert abs(m["wrongful_refusal_rate"] - 1 / 3) < 1e-9
    assert m["refusal_recall"] == 0.5 and m["refusal_precision"] == 0.5
    assert m["ingredient_reason_coverage"] == 1.0 and m["step_reason_coverage"] == 0.5
    v = scoring.verdicts(m)
    assert v["refusal_precision"] == "fail" and v["median_latency_s"] == "pass"


def test_dry_run_makes_no_call(capsys):
    assert run_revision.main([]) == 0
    assert "dry run" in capsys.readouterr().out
