# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Offline tests of the naive-dish scorer and the frozen criteria (no model, no network)."""

import json
from pathlib import Path

import pytest
from experiments.dish_naive import scoring
from experiments.dish_naive.run_naive import hybrid_answers, main, reference, well_formed

from app.dishes.catalog import Catalog

HERE = Path(__file__).resolve().parents[4] / "research" / "experiments"
CRITERIA = json.loads((HERE / "dish_naive" / "criteria.json").read_text(encoding="utf-8"))
OLD_CASES = json.loads((HERE / "dish_eval" / "cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.fixture(scope="module")
def catalog():
    return Catalog.load()


def test_criteria_reuse_the_frozen_suggestion_inputs():
    old = {c["id"]: c["input"]["ingredients"] for c in OLD_CASES if c["endpoint"] == "suggest"}
    ours = {c["id"]: c["ingredients"] for c in CRITERIA["cases"]}
    assert set(ours) == set(old) - {"S28", "S29"}
    assert all(ours[i] == old[i] for i in ours)
    assert CRITERIA["max_model_calls"] == 80
    assert "Not human-labelled" in CRITERIA["ground_truth"]


def test_malformed_cases_are_refused_by_the_request_model():
    for case in CRITERIA["cases"]:
        assert well_formed(case["ingredients"]) == (case["expect_status"] == 200)


def test_owned_matching_is_exact_or_synonym_after_trimming():
    owned = scoring.owned_set(["달걀", " 김 치 "])
    assert scoring.is_owned("계란", owned) and scoring.is_owned("김치", owned)
    assert not scoring.is_owned("대파", owned) and not scoring.is_owned(" ", owned)
    assert scoring.have_subset(["계란"], owned) and not scoring.have_subset(["소금"], owned)
    assert scoring.have_subset(["소금"], owned, frozenset({"소금"}))
    assert scoring.missing_disjoint(["대파"], owned) and not scoring.missing_disjoint(
        ["달걀"], owned
    )


def test_case_result_and_aggregate():
    names = {"김치죽", "김치볶음밥"}
    dishes = [
        {"id": "a", "have": ["김치"], "missing": []},
        {"id": "b", "have": ["밥"], "missing": ["김치"]},  # have not owned, missing owned
    ]
    r = scoring.case_result(
        ["김치죽", "없는요리", "김치볶음밥"],
        dishes,
        ["김치"],
        names,
        {"a", "z"},
        {"a": 0, "b": 3},
        frozenset(),
    )
    assert r["raw_names_valid"] == 2 and r["have_ok"] == 1 and r["missing_ok"] == 1
    assert r["reference_hits"] == 1 and r["le2_missing"] == 1
    empty = scoring.case_result([], [], ["x"], names, {"a"}, {}, frozenset())
    m = scoring.aggregate([r, empty])
    assert m["valid_names_share"] == pytest.approx(2 / 3) and m["nonempty_when_possible"] == 0.5
    assert m["reference_recall"] == pytest.approx(1 / 3) and m["reference_precision"] == 0.5
    verdict = scoring.verdict(
        m, {"valid_names_share": {"min": 1.0}, "median_latency_s": {"max": 5}}
    )
    assert verdict == {"valid_names_share": False, "median_latency_s": None}


def test_reference_is_complete_or_one_missing(catalog):
    ids = reference(catalog, ["김치", "밥"])
    assert "kimchi-porridge" in ids and "bibimbap" not in ids
    assert reference(catalog, ["소금"]) == set()


def test_hybrid_answers_are_read_from_a_stored_summary(tmp_path):
    path = tmp_path / "s.json"
    path.write_text(
        json.dumps(
            {
                "cases": [
                    {"id": "S01", "endpoint": "suggest", "response": {"dishes": [{"id": "x"}]}},
                    {"id": "S27", "endpoint": "suggest"},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert hybrid_answers(path) == {"S01": ["x"]}
    assert hybrid_answers(None) == {} and hybrid_answers(tmp_path / "missing.json") == {}


def test_dry_run_makes_no_call(capsys):
    assert main([]) == 0
    assert "29 cases, 27 model calls planned" in capsys.readouterr().out
