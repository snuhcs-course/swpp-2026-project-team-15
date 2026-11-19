# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Offline tests of study v2: ranking, selection, judge parsing, kappa, bootstrap, the rule."""

import json
from pathlib import Path

import pytest
from experiments.youtube_discovery_v2 import run, scoring

HERE = Path(__file__).resolve().parents[4] / "research" / "experiments" / "youtube_discovery_v2"
CRIT = json.loads((HERE / "criteria.json").read_text(encoding="utf-8"))


def cand(
    i, views=100, likes=10, ch="c", published="2026-01-01", usable=True, title="t", hangul=True
):
    return {
        "video_id": i,
        "title": title,
        "channel_id": ch,
        "views": views,
        "likes": likes,
        "published_at": published,
        "usable": usable,
        "hangul_title": hangul,
    }


def test_duration_and_short():
    assert scoring.duration_seconds("PT1M5S") == 65
    assert scoring.duration_seconds("PT45S") == 45
    assert scoring.duration_seconds("PT1H2M3S") == 3723
    assert scoring.duration_seconds("P0D") is None
    assert scoring.is_short({"duration_s": 60}) and not scoring.is_short({"duration_s": 61})
    assert not scoring.is_short({"duration_s": None})


def test_to_candidate_flags_unusable():
    item = {
        "id": "x" * 11,
        "snippet": {
            "title": "Kimchi fried rice",
            "description": "d" * 900,
            "tags": list("abcdefghij"),
        },
        "status": {"embeddable": False, "privacyStatus": "public"},
        "statistics": {"viewCount": "12"},
        "contentDetails": {"duration": "PT30S"},
    }
    c = scoring.to_candidate(item)
    assert not c["usable"] and not c["hangul_title"] and len(c["description"]) == 500
    assert len(c["tags"]) == 8 and c["views"] == 12 and c["likes"] is None


def test_rankings():
    vs = [
        cand("a", views=500, likes=5, ch="x", published="2026-01-01"),
        cand("b", views=400, likes=200, ch="x", published="2026-03-01"),
        cand("c", views=300, likes=3, ch="y", published="2026-02-01"),
        cand("d", views=50, likes=40, ch="z", published="2026-04-01"),
    ]
    assert [c["video_id"] for c in scoring.rank(vs, "views")] == ["a", "b", "c"]
    # d has fewer than 1000 views so its ratio is ignored; b has the best ratio above the floor
    big = [{**c, "views": c["views"] * 10} for c in vs]
    assert scoring.rank(big, "like_ratio")[0]["video_id"] == "b"
    assert [c["video_id"] for c in scoring.rank(vs, "recency")] == ["d", "b", "c"]
    # one video per channel first, repeats only fill empty slots
    assert [c["video_id"] for c in scoring.rank(vs, "views_channel")] == ["a", "c", "d"]
    assert [c["video_id"] for c in scoring.rank(vs[:2], "views_channel")] == ["a", "b"]
    with pytest.raises(ValueError):
        scoring.rank(vs, "nope")


def test_choose_filters_unusable_and_irrelevant():
    vs = [cand("a", views=9, usable=False), cand("b", views=5), cand("c", views=7)]
    got = scoring.choose(vs, lambda c: c["video_id"] != "c", "views")
    assert [c["video_id"] for c in got] == ["b"]


def test_precision_counts_empty_slots_as_misses():
    chosen = [cand("a"), cand("b")]
    assert scoring.precision_at(chosen, lambda c: c["video_id"] == "a") == pytest.approx(1 / 3)
    assert scoring.precision_at([], lambda c: True) == 0.0


def test_kappa():
    t = [True, True, False, False]
    assert scoring.cohen_kappa(t, t) == 1.0
    assert scoring.cohen_kappa(t, [not x for x in t]) == -1.0
    assert scoring.cohen_kappa([True, True], [True, True]) is None
    assert scoring.cohen_kappa([], []) is None
    conf = scoring.confusion(t, [True, False, False, True])
    assert (conf["tp"], conf["fp"], conf["fn"], conf["tn"]) == (1, 1, 1, 1)


def test_parse_judgements_is_strict():
    keys = ["a", "b"]
    ok = (
        '```json\n{"judgements":[{"i":"a","relevant":true,"reason":"x"},'
        '{"i":"b","relevant":false}]}\n```'
    )
    assert scoring.parse_judgements(ok, keys) == {"a": True, "b": False}
    assert scoring.parse_judgements('{"judgements":[{"i":"a","relevant":true}]}', keys) is None
    dup = '{"judgements":[{"i":"a","relevant":true},{"i":"a","relevant":true}]}'
    assert scoring.parse_judgements(dup, keys) is None
    assert (
        scoring.parse_judgements(
            '{"judgements":[{"i":"a","relevant":"yes"},{"i":"b","relevant":true}]}', keys
        )
        is None
    )
    assert scoring.parse_judgements("not json", keys) is None


def test_extract_ids_limit_and_shorts():
    txt = " ".join(f"https://youtu.be/{c * 11}" for c in "abcdefghijklmnop")
    assert len(scoring.extract_ids(txt, [])) == 12
    assert scoring.extract_ids("", ["https://youtube.com/shorts/" + "Z" * 11]) == ["Z" * 11]


def test_bootstrap_interval_contains_zero_for_identical_and_not_for_clear_gain():
    same = [0.3, 0.6, 0.0, 1.0]
    mean, lo, hi = scoring.bootstrap_diff(same, same, seed=1, reps=500)
    assert mean == 0 and lo == 0 == hi
    mean, lo, hi = scoring.bootstrap_diff([1.0] * 10, [0.0] * 10, seed=1, reps=500)
    assert mean == 1.0 and lo == 1.0


def test_decide_applies_the_coverage_gate_then_p3_then_cost():
    table = {
        "base": {"coverage": 0.8, "p3": 0.4, "cost": 0.0, "search_calls": 1},
        "bigp3_lowcov": {"coverage": 0.5, "p3": 0.9, "cost": 0.0, "search_calls": 0},
        "good": {"coverage": 0.75, "p3": 0.6, "cost": 0.01, "search_calls": 0},
        "good_cheaper": {"coverage": 0.75, "p3": 0.6, "cost": 0.0, "search_calls": 1},
    }
    per = {k: [0.6, 0.6, 0.6, 0.6] for k in table}
    per["base"] = [0.4, 0.4, 0.4, 0.4]
    out = scoring.decide(table, "base", seed=3, per_dish_p3=per)
    assert out["winner"] == "good_cheaper" and out["eligible"] == 3
    assert out["vs_baseline"]["verdict"] == "better"
    per["good_cheaper"] = [0.4, 0.4, 0.4, 0.4]
    assert scoring.decide(table, "base", 3, per)["vs_baseline"]["verdict"] == "inconclusive"


def test_criteria_match_study_v1_sample_and_combination_count():
    v1 = json.loads(
        (HERE.parent / "youtube_discovery" / "criteria.json").read_text(encoding="utf-8")
    )["sample"]
    assert len(v1["cached"]) + len(v1["extra"]) == 40
    assert CRIT["seed"] == 20261116 and CRIT["baseline"] == "A1|J0|views"
    assert CRIT["budget"]["search_list_calls"] == 20
    assert 4 * 2 * len(scoring.RANKINGS) == 32


def test_dry_run_makes_no_call(capsys, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("network used")

    monkeypatch.setattr(run.httpx, "Client", boom)
    for cmd in ("plan", "collect", "judge", "judge-validate"):
        assert run.main([cmd]) == 0
    assert "dry run" in capsys.readouterr().out


def test_one_combo_scores_choice_by_the_selector_and_precision_by_the_evaluator():
    from experiments.youtube_discovery_v2 import analyze

    def vid(i, views, title):
        return {**cand(i, views=views, title=title), "channel_id": i}

    store = {
        "d1": {
            "methods": {"B": ["a", "b", "c"]},
            "cost": {"B": {"cost": 0.01}},
            "videos": {
                "a": vid("a", 30, "김치볶음밥 레시피"),
                "b": {**vid("b", 20, "Kimchi fried rice"), "hangul_title": False},
                "c": vid("c", 10, "다른 요리"),
            },
        }
    }
    judged = {
        "d1": {
            "J1": {"judgements": {"a": True, "b": True, "c": False}, "cost": 0.002},
            "E": {"judgements": {"a": True, "b": True, "c": False}},
        }
    }
    table = {"d1": {"name": "김치볶음밥"}}
    p3j0, stats0 = analyze.one_combo(store, judged, table, ["d1"], ("B", "J0", "views"))
    p3j1, stats1 = analyze.one_combo(store, judged, table, ["d1"], ("B", "J1", "views"))
    assert p3j0 == [pytest.approx(1 / 3)] and stats0["english_relevant_chosen"] == 0
    assert p3j1 == [pytest.approx(2 / 3)] and stats1["english_relevant_chosen"] == 1
    assert stats1["cost"] == pytest.approx(0.012) and stats1["coverage"] == 0.0
