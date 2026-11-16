# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Offline tests of round 3: request texts, link features, scorers and the frozen rule."""

import json
from pathlib import Path

import pytest
from experiments.dish_pipeline import round3 as r3

ROOT = Path(__file__).resolve().parents[4]
CRITERIA = json.loads(
    (ROOT / "research/experiments/dish_pipeline/criteria_round3.json").read_text("utf-8")
)
CATALOG = json.loads((ROOT / "server/app/dishes/dishes.json").read_text("utf-8"))["dishes"]
A, B = "abcdefghijk", "ABCDEFGHIJK"


def test_request_texts_differ_only_in_the_frozen_way():
    d0, d1, d2, d3 = (r3.request_text(v, "김치볶음밥") for v in r3.VARIANTS)
    assert "자취생" in d1 and all("자취" not in t for t in (d0, d2, d3))
    assert "김치볶음밥" in d0 and "이웃 요리" in d3 and "이웃 요리" not in d2
    assert "길이가 짧은" in d2 and "길이가 짧은" in d3 and "길이가 짧은" not in d1
    assert all("최대 8개" in t and "watch?v=" in t for t in (d0, d1, d2, d3))
    with pytest.raises(ValueError):
        r3.request_text("D9", "x")


def test_criteria_hold_the_exact_texts_and_the_dishes():
    for v in r3.VARIANTS:
        assert CRITERIA["exact_request_texts"][v] == r3.request_text(v, "<dish>")
    ids = {d["id"] for d in CATALOG}
    listed = CRITERIA["dishes"]["list"]
    assert len(listed) == 27 and len(set(listed)) == 27 and set(listed) <= ids


def test_ids_come_from_the_answer_then_the_citations():
    text = f"[{{'url': 'https://www.youtube.com/watch?v={A}'}}] https://youtu.be/{B}"
    cite = [f"https://www.youtube.com/shorts/{'0123456789_'}", f"https://youtube.com/watch?v={A}"]
    assert r3.extract_ids(text, cite) == [A, B, "0123456789_"]
    assert r3.extract_ids("no ids", []) == [] and len(r3.extract_ids(text * 20, [], limit=1)) == 1


def test_duration_and_candidate_features():
    assert r3.duration_seconds("PT1H2M3S") == 3723 and r3.duration_seconds("PT45S") == 45
    assert r3.duration_seconds("P0D") is None and r3.duration_seconds(None) is None
    item = {
        "id": A,
        "snippet": {"title": "자취 볶음밥", "tags": ["자취요리"]},
        "contentDetails": {"duration": "PT59S"},
        "statistics": {"viewCount": "10"},
        "status": {"embeddable": True, "privacyStatus": "public"},
    }
    c = r3.to_candidate(item)
    assert c["usable"] and r3.is_short(c) and r3.has_jachwi(c) and c["views"] == 10
    item["status"]["embeddable"] = False
    assert not r3.to_candidate(item)["usable"]
    assert not r3.has_jachwi({"title": "볶음밥", "tags": ["한식"]})


def test_failure_types_follow_the_pre_set_order():
    dish = next(d for d in CATALOG if d["id"] == "kimchi-tuna-fried-rice")
    near = next(d for d in CATALOG if d["id"] == "kimchi-fried-rice")
    far = next(d for d in CATALOG if d["category"] != dish["category"])
    base = {"title": "", "tags": [], "duration_s": 600}

    def t(**kw):
        return r3.failure_type({**base, **kw}, dish, CATALOG)

    assert t(duration_s=30, title="x") == "short"
    assert t(title="아침 브이로그") == "vlog_or_show"
    assert t(title=f"{near['name']} 레시피") == "neighbour_dish"
    assert t(title=f"{far['name']} 레시피") == "other_dish"
    assert t(title="아무 영상") == "other" and t(title=dish["name"]) == "other"


def test_parse_judgements_needs_every_key_once():
    ok = '{"judgements":[{"i":"a","relevant":true,"reason":"x"},{"i":"b","relevant":false}]}'
    assert r3.parse_judgements(ok, ["a", "b"]) == {"a": True, "b": False}
    assert r3.parse_judgements(ok, ["a"]) is None and r3.parse_judgements("x", ["a"]) is None
    bad = '{"judgements":[{"i":"a","relevant":"yes"}]}'
    assert r3.parse_judgements(bad, ["a"]) is None


def row(rels, durations=None, cost=0.01):
    durations = durations or [600] * len(rels)
    links = [
        {"duration_s": d, "title": "", "tags": [], "rel": {"E": r, "J1": r}}
        for r, d in zip(rels, durations, strict=True)
    ]
    return {"links": links, "provided": len(rels), "exist": len(rels), "cost": cost,
            "latency_s": 3.0, "error": False}  # fmt: skip


def test_variant_metrics():
    m = r3.variant_metrics([row([True, False]), row([]), row([True], [30])], "E")
    assert m["usable"] == 3 and m["relevant"] == 2 and m["relevant_share"] == pytest.approx(2 / 3)
    assert m["dishes_with_relevant"] == 2 and m["first_link_relevant"] == 1.0
    assert m["shorts_share"] == pytest.approx(1 / 3) and m["usable_per_dish"] == 1.0
    assert m["duration_s_quartiles"][1] == 600 and m["errors"] == 0
    empty = r3.variant_metrics([row([])], "E")
    assert empty["relevant_share"] is None and empty["first_link_relevant"] is None


def test_pooled_diff_is_zero_for_equal_inputs_and_positive_for_better():
    same = [row([True, False]) for _ in range(10)]
    mean, lo, hi = r3.pooled_diff(same, same, "E", seed=1, reps=500)
    assert mean == 0 and lo <= 0 <= hi
    better = [row([True, True]) for _ in range(10)]
    mean, lo, hi = r3.pooled_diff(better, same, "E", seed=1, reps=500)
    assert mean == pytest.approx(0.5) and lo > 0


def test_decide_applies_eligibility_cost_and_interval():
    def m(share, dishes, per, cost=0.01):
        return {"relevant_share": share, "dishes_with_relevant": dishes,
                "usable_per_dish": per, "cost_per_request": cost}  # fmt: skip

    metrics = {"D0": m(0.7, 20, 3.0), "D1": m(0.9, 17, 3.0), "D2": m(0.8, 20, 2.0),
               "D3": m(0.75, 19, 2.6)}  # fmt: skip
    diffs = {"D1": (0.2, 0.1, 0.3), "D2": (0.1, 0.0, 0.2), "D3": (0.05, 0.01, 0.1)}
    res = r3.decide(metrics, diffs)
    assert res["eligible"] == ["D0", "D3"] and res["winner_by_share"] == "D3"
    assert res["verdict"] == "adopt D3"
    diffs["D3"] = (0.05, -0.02, 0.1)
    assert r3.decide(metrics, diffs)["verdict"] == "inconclusive, keep D0"
    flat = {"D0": m(0.8, 20, 3.0), "D1": m(0.7, 20, 3.0)}
    assert r3.decide(flat, {"D1": (-0.1, -0.2, 0.0)})["verdict"] == "winner is D0"


def test_shuffle_is_seeded_and_complete():
    keys = [str(i) for i in range(10)]
    assert r3.shuffled(keys, 5) == r3.shuffled(keys, 5)
    assert sorted(r3.shuffled(keys, 5)) == sorted(keys)
