# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Offline tests of the output-size variants and their decision helper."""

from experiments.dish_tokens.run_output import (
    STOP_SENTENCE,
    decide,
    payload_for,
    qualifies,
    schema_for,
    split_missing,
)

NAMES = ["김치비빔밥", "계란말이"]


def item(schema):
    return schema["properties"]["dishes"]["items"]


def test_variants_change_only_what_they_claim():
    o2 = payload_for("P0", "O2", ["김치"], NAMES)
    assert o2["messages"][0]["content"].endswith(STOP_SENTENCE)
    assert "max_tokens" in o2 and o2["max_tokens"] == 4096
    o3 = item(schema_for("P0", "O3", ["김치"]))
    assert o3["properties"]["missing"] == {"type": "string"}
    o1 = item(schema_for("P0", "O1", ["김치"]))
    assert set(o1["properties"]) == {"name", "missing"} and o1["required"] == ["name", "missing"]


def test_split_missing_trims_and_leaves_lists_alone():
    data = {"dishes": [{"name": "a", "have": [], "missing": " 두부 , 대파,, "}, {"missing": ["x"]}]}
    out = split_missing(data)
    assert out["dishes"][0]["missing"] == ["두부", "대파"] and out["dishes"][1]["missing"] == ["x"]
    assert data["dishes"][0]["missing"] == " 두부 , 대파,, "


def variant(cost, recall=0.4, failed=0, truncated=0):
    return {
        "failed": failed,
        "truncated": truncated,
        "mean_cost_usd": cost,
        "metrics": {"reference_recall": recall, "have_subset_share": 1.0},
    }


def test_decision_prefers_cheaper_qualifying_adoptable_variant():
    base = variant(0.0006)
    assert qualifies(variant(0.0004, recall=0.39), base)
    assert not qualifies(variant(0.0004, recall=0.37), base)
    assert not qualifies(variant(0.0004, truncated=1), base)
    result = decide(
        {"O0": base, "O1": variant(0.0003), "O2": variant(0.0005), "O3": variant(0.0004)}
    )
    assert result["adopted"] == "O3"
    assert decide({"O0": base, "O1": variant(0.0003), "O2": variant(0.0007)})["adopted"] is None
