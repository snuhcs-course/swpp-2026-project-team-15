# AI-generated with Claude Code (Opus 5.5), 2026-10-14; review pending by Jaehyuk Choi.
from evaluation.vision_benchmark import score


def test_score_counts_items_found_by_any_accepted_name():
    expected = {
        "콜라": ["콜라", "탄산음료"],
        "닥터페퍼": ["닥터페퍼", "탄산음료"],
        "와인": ["와인"],
    }

    result = score(expected, ["탄산음료", "우유"])

    assert result == {
        "found": ["콜라", "닥터페퍼"],
        "missed": ["와인"],
        "unmatched_candidates": ["우유"],
    }


def test_score_matches_accepted_name_inside_candidate():
    assert score({"순살치킨": ["치킨"]}, ["냉동 치킨"])["found"] == ["순살치킨"]
