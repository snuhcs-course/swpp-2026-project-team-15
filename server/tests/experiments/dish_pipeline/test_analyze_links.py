# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Offline tests of the round-2 link analysis with a tiny fabricated data set."""

from experiments.dish_pipeline.analyze_links import (
    agreement,
    kappa,
    per_dish,
    rejected_links,
    summarise,
    title_rule,
)

NAMES = {"d1": "김치볶음밥", "d2": "계란말이"}


def video(title, usable=True):
    return {"title": title, "channel": "c", "duration_s": 100, "usable": usable}


CANDIDATES = {
    "d1": {
        "methods": {"B": ["a", "b", "c", "x"], "B2": ["a"]},
        "videos": {
            "a": video("김치 볶음밥 레시피"),
            "b": video("Kimchi fried rice"),
            "c": video("blocked", usable=False),
        },
    },
    "d2": {
        "methods": {"B": ["e"], "B2": ["e"]},
        "videos": {"e": video("계란말이 쉽게")},
    },
}
JUDGEMENTS = {
    "d1": {
        "E": {"judgements": {"a": True, "b": True}},
        "J1": {"judgements": {"a": True, "b": False}},
    },
    "d2": {"E": {"judgements": {"e": False}}, "J1": {"judgements": {"e": False}}},
}


def test_title_rule_ignores_spaces_and_case():
    assert title_rule("김치 볶음밥 만들기", "김치볶음밥")
    assert not title_rule("Kimchi fried rice", "김치볶음밥")


def test_counts_follow_the_check_and_the_judge():
    rows = per_dish(CANDIDATES, JUDGEMENTS, NAMES, "B", "E")
    d1 = next(r for r in rows if r["dish"] == "d1")
    assert d1["provided"] == 4 and d1["exist"] == 3
    assert d1["usable"] == ["a", "b"] and d1["relevant"] == ["a", "b"] and d1["j0"] == ["a"]
    s = summarise(rows)
    assert s["links_usable"] == 3 and s["links_relevant"] == 2
    assert s["dishes_with_0_1_2_3plus_relevant"] == [1, 0, 1, 0]
    assert s["judge_accepts_but_j0_rejects"] == 1 and s["j0_accepted_but_judge_rejects"] == 1
    assert s["first_usable_link_relevant_share"] == 0.5


def test_agreement_and_rejected_list():
    rows = per_dish(CANDIDATES, JUDGEMENTS, NAMES, "B", "E")
    ag = agreement(rows, CANDIDATES, JUDGEMENTS)
    assert ag["links"] == 3 and ag["relevant_by_E"] == 2 and ag["relevant_by_J1"] == 1
    assert [r["id"] for r in rejected_links(rows, CANDIDATES)] == ["e"]


def test_kappa_edge_cases():
    assert kappa([], []) is None
    assert kappa([True, True], [True, True]) is None
    assert kappa([True, False], [True, False]) == 1.0
