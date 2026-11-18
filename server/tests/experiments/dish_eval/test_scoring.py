# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Offline tests of the dish-evaluation scorer, the case file and the thresholds (no model, no network)."""

import json
from pathlib import Path

import pytest
from experiments.dish_eval import scoring
from experiments.dish_eval.run_eval import FailingLLM, View, main

from app.dishes.catalog import Catalog

HERE = Path(__file__).resolve().parents[4] / "research" / "experiments" / "dish_eval"
CASES = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["cases"]
THRESHOLDS = json.loads((HERE / "thresholds.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog():
    # the cases were frozen against this catalog (130 dishes); the live one has two dishes fewer
    return Catalog.load(HERE / "catalog_at_freeze.json")


@pytest.fixture(scope="module")
def view(catalog):
    return View(catalog)


def dish(view, dish_id, have=(), missing=()):
    return {
        "id": dish_id,
        "name": "x",
        "category": "c",
        "have": list(have),
        "missing": list(missing),
        "reason": "r",
        "keywords": [],
        "videos": [],
        "search_url": "u",
    }


def case(**kw):
    base = {
        "input": {"ingredients": ["김치", "밥"], "limit": 5},
        "acceptable_dish_ids": ["kimchi-rolled"],
    }
    base.update(kw)
    return base


# ---- the frozen files -------------------------------------------------------------------


def test_case_counts_and_ids_unique():
    suggest = [c for c in CASES if c["endpoint"] == "suggest"]
    adapt = [c for c in CASES if c["endpoint"] == "adapt"]
    assert len(CASES) >= 36 and len(suggest) >= 28 and len(adapt) >= 8
    assert len({c["id"] for c in CASES}) == len(CASES)


def test_cases_reference_real_dishes(catalog):
    for c in CASES:
        if c["endpoint"] == "suggest" and c["expect_status"] == 200:
            for key in ("acceptable_dish_ids", "must_not_include"):
                assert all(i in catalog.dishes for i in c.get(key, [])), c["id"]
            assert not set(c["acceptable_dish_ids"]) & set(c["must_not_include"]), c["id"]
            assert c["acceptable_dish_ids"] or c.get("expect_empty"), c["id"]
        if c["endpoint"] == "adapt" and c["input"]["dish_id"] != "no-such-dish":
            assert c["input"]["dish_id"] in catalog.dishes, c["id"]


def test_labels_match_the_table(catalog):
    """The labelled acceptable sets are exactly the dishes with at most one missing key item."""
    for c in CASES:
        if c["endpoint"] != "suggest" or c["expect_status"] != 200:
            continue
        owned = catalog.owned(c["input"]["ingredients"])
        ok = {
            m.dish.id
            for m in (catalog.match(d, owned) for d in catalog.dishes.values())
            if m.have and len(m.missing) <= 1
        }
        assert ok == set(c["acceptable_dish_ids"]), c["id"]


def test_thresholds_cover_every_metric():
    keys = {f"{g}.{n}" for g in ("suggest", "adapt") for n in THRESHOLDS[g]}
    metrics = scoring.aggregate([], [], [], [], [])
    assert keys <= set(metrics)
    for g in ("suggest", "adapt"):
        for spec in THRESHOLDS[g].values():
            assert spec["op"] in (">=", "<=") and spec["rationale"]


def test_dry_run_makes_no_call(capsys):
    assert main([]) == 0
    assert "dry run" in capsys.readouterr().out


def test_live_run_needs_flag(capsys):
    assert main(["--provider", "llm"]) == 2


# ---- suggest scoring --------------------------------------------------------------------


def test_good_suggest_passes(view):
    r = {"source": "llm", "dishes": [dish(view, "kimchi-rolled", ["밥", "김치"], ["김", "참기름"])]}
    out = scoring.check_suggest(case(), r, view)
    assert out["schema_valid"] and out["ids_in_catalog"] and out["have_missing_consistent"]
    assert out["acceptable_in_top5"] and out["dishes_le2_missing"] == 1


def test_unknown_id_and_bad_schema(view):
    r = {"source": "llm", "dishes": [dish(view, "made-up")]}
    out = scoring.check_suggest(case(), r, view)
    assert out["schema_valid"] and not out["ids_in_catalog"] and not out["have_missing_consistent"]
    broken = {"source": "x", "dishes": []}
    assert not scoring.check_suggest(case(), broken, view)["schema_valid"]
    many = {"source": "llm", "dishes": [dish(view, "kimchi-rolled")] * 6}
    assert scoring.check_suggest(case(), many, view)["schema_valid"]  # no length cap any more


def test_inconsistent_have_missing(view):
    both = dish(view, "kimchi-rolled", ["밥"], ["밥"])
    assert not scoring.check_suggest(case(), {"source": "llm", "dishes": [both]}, view)[
        "have_missing_consistent"
    ]
    alien = dish(view, "kimchi-rolled", ["밥", "연어"], [])
    assert not scoring.check_suggest(case(), {"source": "llm", "dishes": [alien]}, view)[
        "have_missing_consistent"
    ]
    owned_missing = dish(view, "kimchi-rolled", ["밥"], ["김치"])
    assert not scoring.check_suggest(case(), {"source": "llm", "dishes": [owned_missing]}, view)[
        "have_missing_consistent"
    ]


def test_acceptable_only_counts_top5_and_forbidden(view):
    filler = [dish(view, "kimchi-stew") for _ in range(5)]
    late = {"source": "rules", "dishes": filler + [dish(view, "kimchi-rolled")]}
    c = case(input={"ingredients": ["김치", "밥"], "limit": 8}, must_not_include=["kimchi-stew"])
    out = scoring.check_suggest(c, late, view)
    assert not out["acceptable_in_top5"] and out["must_not_include_hits"] == 5


def test_expect_empty(view):
    c = case(acceptable_dish_ids=[], expect_empty=True)
    assert scoring.check_suggest(c, {"source": "rules", "dishes": []}, view)["acceptable_in_top5"]
    full = {"source": "rules", "dishes": [dish(view, "kimchi-rolled")]}
    assert not scoring.check_suggest(c, full, view)["acceptable_in_top5"]


# ---- adapt scoring ----------------------------------------------------------------------


def sub(missing, suggestion, uses):
    return {"missing": missing, "suggestion": suggestion, "uses": uses}


def answer(subs=(), skip=(), note="", source="llm"):
    return {
        "dish_id": "d",
        "substitutions": list(subs),
        "skip_ok": list(skip),
        "note": note,
        "source": source,
    }


ALLOWED = case(
    outcome="allowed_substitution",
    allowed_pairs=[{"missing": "대파", "uses": ["양파"]}],
    expected_skip_ok=[],
)


def test_adapt_allowed_pair(catalog):
    good = answer([sub("대파", "양파로 대신해요", ["양파"])])
    out = scoring.check_adapt(ALLOWED, good, catalog.staples)
    assert out["schema_valid"] and out["pairs_in_table"] and out["outcome_match"]
    assert out["no_quantities_or_steps"]


def test_adapt_pair_outside_table(catalog):
    bad = answer([sub("대파", "부추로 대신해요", ["부추"])])
    assert not scoring.check_adapt(ALLOWED, bad, catalog.staples)["pairs_in_table"]
    wrong_missing = answer([sub("계란", "양파로 대신해요", ["양파"])])
    assert not scoring.check_adapt(ALLOWED, wrong_missing, catalog.staples)["pairs_in_table"]


def test_adapt_pantry_items_in_uses_are_ignored(catalog):
    combo = case(
        outcome="allowed_substitution",
        allowed_pairs=[{"missing": "고추장", "uses": ["고춧가루", "간장", "설탕"]}],
        expected_skip_ok=[],
    )
    a = answer([sub("고추장", "고춧가루로 대신해요", ["고춧가루", "간장", "설탕"])])
    assert scoring.check_adapt(combo, a, catalog.staples)["pairs_in_table"]


@pytest.mark.parametrize(
    "text",
    ["양파 1개로 대신해요", "2큰술 넣어요", "먼저 볶아요", "물에 넣고 끓여요", "200g 사용"],
)
def test_adapt_rejects_invented_quantities_or_steps(catalog, text):
    a = answer([sub("대파", text, ["양파"])])
    assert not scoring.check_adapt(ALLOWED, a, catalog.staples)["no_quantities_or_steps"]


def test_adapt_empty_with_note(catalog):
    c = case(outcome="empty_with_note", allowed_pairs=[], expected_skip_ok=[])
    ok = answer(note=scoring.NO_SUBSTITUTE, source="rules")
    assert scoring.check_adapt(c, ok, catalog.staples)["empty_with_note_ok"] is True
    invented = answer([sub("김", "김치로", ["김치"])], note="")
    out = scoring.check_adapt(c, invented, catalog.staples)
    assert out["empty_with_note_ok"] is False and not out["pairs_in_table"]
    assert scoring.check_adapt(c, answer(), catalog.staples)["empty_with_note_ok"] is False


def test_adapt_skip_and_nothing_missing(catalog):
    skip = case(outcome="skip_ok_only", allowed_pairs=[], expected_skip_ok=["당근"])
    assert scoring.check_adapt(skip, answer(skip=["당근"]), catalog.staples)["outcome_match"]
    assert not scoring.check_adapt(skip, answer(), catalog.staples)["outcome_match"]
    none = case(outcome="nothing_missing", allowed_pairs=[], expected_skip_ok=[])
    assert scoring.check_adapt(none, answer(note=scoring.NOTHING_MISSING), catalog.staples)[
        "outcome_match"
    ]


def test_adapt_malformed_and_missing_response(catalog):
    assert not scoring.check_adapt(ALLOWED, None, catalog.staples)["schema_valid"]
    assert not scoring.check_adapt(ALLOWED, {"substitutions": "x"}, catalog.staples)["schema_valid"]


# ---- aggregation and verdict ------------------------------------------------------------


def suggest_row(**kw):
    row = {
        "schema_valid": True,
        "ids_in_catalog": True,
        "have_missing_consistent": True,
        "acceptable_in_top5": True,
        "must_not_include_hits": 0,
        "dishes": 5,
        "dishes_le2_missing": 5,
        "source": "llm",
    }
    row.update(kw)
    return row


def adapt_row(**kw):
    row = {
        "schema_valid": True,
        "pairs_in_table": True,
        "no_quantities_or_steps": True,
        "outcome_match": True,
        "empty_with_note_ok": None,
    }
    row.update(kw)
    return row


def test_aggregate_and_verdict_pass_and_fail():
    suggest = [suggest_row() for _ in range(9)] + [
        suggest_row(acceptable_in_top5=False, dishes_le2_missing=2)
    ]
    adapt = [adapt_row(), adapt_row(empty_with_note_ok=True)]
    m = scoring.aggregate(suggest, [True, True], [True] * 10, adapt, [True], [1.0, 3.0, 9.0])
    assert m["suggest.acceptable_in_top5"] == pytest.approx(0.9)
    assert m["suggest.share_le2_missing"] == pytest.approx(47 / 50)
    assert m["adapt.latency_median_s"] == 3.0
    rows = {r["metric"]: r["status"] for r in scoring.verdict(m, THRESHOLDS)}
    assert rows["suggest.acceptable_in_top5"] == "pass"
    assert rows["adapt.latency_median_s"] == "pass"
    worse = scoring.aggregate(
        [suggest_row(must_not_include_hits=1, acceptable_in_top5=False)],
        [False],
        [False],
        [adapt_row(pairs_in_table=False)],
        [True],
    )
    rows = {r["metric"]: r["status"] for r in scoring.verdict(worse, THRESHOLDS)}
    assert rows["suggest.must_not_include_hits"] == "fail"
    assert rows["suggest.invalid_inputs_rejected"] == "fail"
    assert rows["suggest.fallback_valid"] == "fail"
    assert rows["adapt.pairs_in_table"] == "fail"
    assert rows["adapt.latency_median_s"] == "not measured"


# ---- the fallback path and the baseline use real code, with no model ---------------------


def test_failing_model_has_no_rules_fallback_in_the_naive_service(catalog):
    from app.dishes.llm import DishLLMError
    from app.dishes.service import DishService

    with pytest.raises(DishLLMError):
        DishService(catalog, FailingLLM()).suggest(["김치", "밥"])
