# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Offline tests of the pipeline study helpers: parsing, rule check, rule of choice (no network)."""

import json
from pathlib import Path

from experiments.dish_pipeline import discovery as d
from experiments.dish_pipeline.run_pipeline import aggregate, choose, main, percentile

CRITERIA = json.loads(
    (
        Path(__file__).resolve().parents[4] / "research/experiments/dish_pipeline/criteria.json"
    ).read_text(encoding="utf-8")
)
A, B, C = "abcdefghijk", "ABCDEFGHIJK", "01234567890"


def test_ids_come_from_ids_urls_and_titled_items():
    values = [A, f"https://www.youtube.com/watch?v={B}", {"id": C, "title": "t"}, A, 5, "short"]
    assert d.clean_ids(values) == [A, B, C]


def test_parse_dishes_keeps_first_name_and_both_shapes():
    data = {
        "dishes": [
            {"name": "김치죽", "video_ids": [A], "have": ["김치"], "missing": []},
            {"name": "김치죽", "video_ids": [B]},
            {"name": "계란말이", "videos": [{"id": C, "title": "x"}]},
            {"video_ids": [A]},
        ]
    }
    parsed = d.parse_dishes(data)
    assert parsed["김치죽"]["ids"] == [A] and parsed["계란말이"]["ids"] == [C]
    assert d.parse_dishes(None) == {}


def test_extract_json_handles_fences():
    assert d.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert d.extract_json("no json") is None and d.extract_json("{bad}") is None


def test_rule_check_keeps_order_and_drops_unavailable_ids():
    items = {
        A: {
            "id": A,
            "status": {"embeddable": True, "privacyStatus": "public"},
            "snippet": {"title": "t1"},
        },
        B: {"id": B, "status": {"embeddable": False, "privacyStatus": "public"}, "snippet": {}},
        C: {"id": C, "status": {"embeddable": True, "privacyStatus": "private"}, "snippet": {}},
    }
    seen = []

    def fetch(ids):
        seen.append(list(ids))
        return [items[i] for i in ids if i in items]

    check = d.apply_rule_check({"김치죽": [B, A, "zzzzzzzzzzz", C], "빈": []}, fetch)
    assert check["kept"] == {"김치죽": [A], "빈": []}
    assert check["returned_ids"] == 4 and check["existing_ids"] == 3 and check["list_calls"] == 1
    assert len(seen) == 1


def test_ids_are_batched_by_fifty():
    ids = [f"{i:011d}" for i in range(120)]
    batches = []
    d.check_ids(ids, lambda batch: batches.append(len(batch)) or [])
    assert batches == [50, 50, 20]


def _row(cost, latency, share):
    return {
        "dishes": 10,
        "dishes_with_link": int(10 * share),
        "links_kept": 20,
        "returned_ids": 30,
        "existing_ids": 30,
        "failed": False,
        "judged": 0,
        "judged_relevant": 0,
        "input_tokens": 1,
        "output_tokens": 1,
        "reasoning_tokens": 0,
        "cost_usd": cost,
        "cards_latency_s": latency,
        "videos_latency_s": latency,
    }


def test_choice_follows_the_preregistered_rule():
    variants = {
        "P1-ids3": aggregate([_row(0.30, 2, 1.0)]),
        "P2-ids3": aggregate([_row(0.02, 2, 0.95)]),
        "P3-ids3": aggregate([_row(0.01, 9, 1.0)]),  # too slow
        "P2-ids5": aggregate([_row(0.005, 2, 0.5)]),  # too few dishes with a link
        "P4-ids3-open1": aggregate([_row(0.001, 2, 1.0)]),  # reported, never ranked
    }
    assert choose(variants) == "P2-ids3"
    assert choose({"P2-ids3": aggregate([_row(0.02, 2, 0.5)])}) is None
    assert percentile([1, 2, 3, 4], 0.5) in (2, 3) and percentile([], 0.5) is None


def test_criteria_and_dry_run(capsys):
    assert (
        len(CRITERIA["inputs"]["input_ids"]) == 12 and CRITERIA["max_additional_model_calls"] == 200
    )
    assert main([]) == 0
    assert "dry run" in capsys.readouterr().out
