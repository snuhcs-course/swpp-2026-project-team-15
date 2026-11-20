# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
from experiments.dish_naive.run_round2 import payload_for
from experiments.dish_naive.run_round2b import decide, dish_counts


def variant(**over):
    base = {
        "metrics": {
            "valid_names_share": 1.0,
            "have_subset_share": 1.0,
            "nonempty_when_possible": 0.9,
            "reference_recall": 0.5,
            "reference_precision": 0.4,
        },
        "truncated": 0,
        "failed": 0,
        "mean_cost_usd": 0.0005,
        "rows": [],
    }
    metrics = over.pop("metrics", {})
    base["metrics"].update(metrics)
    base.update(over)
    return base


def test_adopts_p1_when_every_check_holds():
    out = decide({"P0": variant(metrics={"have_subset_share": 0.95}), "P1": variant()})
    assert out["adopted"] == "P1" and out["failed_checks"] == []


def test_names_each_failed_check_and_keeps_cap_only_when_p0_is_clean():
    p1 = variant(truncated=1, mean_cost_usd=0.001, metrics={"reference_recall": 0.3})
    out = decide({"P0": variant(), "P1": p1})
    assert out["adopted"] is None
    assert set(out["failed_checks"]) == {
        "no_truncation_or_failure",
        "recall>=P0-0.02",
        "cost<=1.15xP0",
    }
    assert out["p0_cap_only"] is True


def test_cap_only_is_false_when_p0_is_still_truncated():
    out = decide({"P0": variant(truncated=2), "P1": variant(failed=1)})
    assert out["adopted"] is None and out["p0_cap_only"] is False


def test_dish_counts_and_cap_parameter():
    rows = [
        {"id": "S01", "ok": True, "returned": [1, 2, 3]},
        {"id": "S02", "ok": True, "returned": [1]},
        {"id": "S03", "ok": False, "returned": []},
    ]
    counts = dish_counts({"rows": rows})
    assert (counts["min"], counts["median"], counts["max"]) == (1, 2.0, 3)
    assert payload_for("P0", ["두부"], ["두부부침"], 8192)["max_tokens"] == 8192
    assert payload_for("P0", ["두부"], ["두부부침"])["max_tokens"] == 4096
