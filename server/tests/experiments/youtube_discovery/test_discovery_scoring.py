# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Offline tests of the discovery-study scorer, the sampler and the frozen criteria."""

import json
from pathlib import Path

from experiments.youtube_discovery import sampling, scoring

HERE = Path(__file__).resolve().parents[4] / "research" / "experiments" / "youtube_discovery"
CRIT = json.loads((HERE / "criteria.json").read_text(encoding="utf-8"))


def test_norm_ignores_spaces_and_punctuation():
    assert scoring.names_dish("[백종원] 김치 볶음밥, 쉽게!", "김치볶음밥")
    assert not scoring.names_dish("참치마요 덮밥", "김치볶음밥")
    assert not scoring.names_dish("anything", "")


def test_extract_ids_dedupes_and_reads_citations():
    text = '[{"u":"https://www.youtube.com/watch?v=abcDEF12345"}] https://youtu.be/zzzzzzzzzzz'
    cites = [
        "https://youtube.com/watch?v=abcDEF12345&t=3",
        "https://youtube.com/shorts/QQQQQQQQQQQ",
    ]
    assert scoring.extract_ids(text, cites) == ["abcDEF12345", "zzzzzzzzzzz", "QQQQQQQQQQQ"]
    assert scoring.extract_ids("no ids", []) == []


def test_keep_top_filters_names_and_sorts_by_views():
    vs = [
        {"title": "김치볶음밥", "view_count": 5},
        {"title": "other", "view_count": 999},
        {"title": "김치 볶음밥 2", "view_count": 50},
        {"title": "김치볶음밥 3", "view_count": None},
    ]
    assert [v["view_count"] for v in scoring.keep_top(vs, "김치볶음밥", 2)] == [50, 5]


def _row(**kw):
    base = {
        "extracted": None,
        "existing": 3,
        "embeddable": 3,
        "named": 3,
        "named_loose": 3,
        "kept_views": [10, 20, 30],
        "kept": 3,
        "cost_usd": 0.0,
        "search_calls": 0,
        "videos_calls": 1,
        "latency_s": [1.0],
    }
    return {**base, **kw}


def test_summarize_and_decide():
    a = scoring.summarize([_row(search_calls=1, named=2), _row(search_calls=1, kept=2)])
    assert a["relevance_strict"] == 5 / 6 and a["coverage"] == 0.5 and a["quota_units"] == 202
    b = scoring.summarize([_row(extracted=4, existing=4, embeddable=4, named=4, cost_usd=0.01)])
    assert b["existence_rate"] == 1.0 and b["cost_usd_per_dish"] == 0.01
    assert scoring.decide(a, b, CRIT["decision_rule"])["passes"]
    worse = {**b, "existence_rate": 0.9}
    assert not scoring.decide(a, worse, CRIT["decision_rule"])["passes"]


def test_sample_is_reproducible_and_frozen():
    raw = json.loads(
        (Path(__file__).resolve().parents[3] / "app" / "dishes" / "dishes.json").read_text("utf-8")
    )["dishes"]
    s = CRIT["sample"]
    again = sampling.build_sample(raw, s["cached"], s["seed"], s["extra_count"])
    assert again["extra"] == s["extra"] and again["quota"] == s["quota"]
    assert len(set(s["cached"]) | set(s["extra"])) == 40
