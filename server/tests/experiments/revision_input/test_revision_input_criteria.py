# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""Pass criteria on synthetic rows with known answers."""

import json
import math

from experiments.revision_input import criteria as cr


def row(arm, case, rep=1, **kw):
    base = {
        "arm": arm,
        "case_id": case,
        "rep": rep,
        "status": "revised",
        "expected": "revise",
        "prompt_tokens": 1000,
        "completion_tokens": 500,
        "latency_s": 2.0,
        "model_calls": 1,
        "cost": 0.0004,
        "inconsistent": False,
        "id_bad": False,
        "unknown_id": False,
        "stale": False,
        "novel": False,
        "safety_applicable": False,
        "safety_retained": None,
    }
    return {**base, **kw}


def rows_for(n, baseline, candidate):
    """Cases alternate between 'should be revised' and 'should be refused'; each row passes
    through ``baseline``/``candidate`` as (case, repeat), after the neutral defaults below."""
    ids = [f"C{i}" for i in range(n)]

    def make(fn, arm, c, i):
        refuse = int(c[1:]) % 2 == 1
        default = row(arm, c, i, expected="refuse" if refuse else "revise")
        default.update(safety_applicable=not refuse, safety_retained=True)
        return {**default, **{k: v for k, v in fn(c, i).items() if k != "arm"}}

    return {
        "original": {c: [make(baseline, "original", c, i) for i in range(2)] for c in ids},
        "cand": {c: [make(candidate, "cand", c, i) for i in range(2)] for c in ids},
    }


def test_thresholds_file_has_every_criterion():
    t = cr.load_thresholds()["criteria"]
    assert set(t) == {
        "prompt_tokens_ratio",
        "id_noncompliance",
        "format_and_consistency",
        "refusal_errors",
        "answer_quality_judge",
        "safety_retained",
        "rejection_of_attempts",
        "latency_cost_ratio",
    }
    assert t["prompt_tokens_ratio"]["max"] == 0.60
    json.dumps(t)  # plain data


def test_clear_improvement_passes_everything_but_the_judge():
    rows = rows_for(
        30,
        lambda c, i: {"id_bad": True, "prompt_tokens": 2000, "latency_s": 3.0},
        lambda c, i: {"prompt_tokens": 800, "latency_s": 1.0, "cost": 0.0002},
    )
    out = cr.evaluate(rows, "cand")
    assert out["answer_quality_judge"]["pass"] is None
    assert all(v["pass"] for k, v in out.items() if k != "answer_quality_judge")
    assert math.isclose(out["prompt_tokens_ratio"]["value"], 0.4)
    assert out["id_noncompliance"]["diff"] == -1.0


def test_regressions_fail_their_criterion():
    rows = rows_for(
        30,
        lambda c, i: {"prompt_tokens": 1000},
        lambda c, i: {"prompt_tokens": 900, "status": "refused", "latency_s": 4.0},
    )
    out = cr.evaluate(rows, "cand")
    assert not out["prompt_tokens_ratio"]["pass"]  # 0.9 > 0.60
    assert not out["refusal_errors"]["pass"]
    assert not out["latency_cost_ratio"]["pass"]


def test_rejection_rate_counts_attempts_only():
    rows = rows_for(
        20,
        lambda c, i: {},
        lambda c, i: {"status": "check_failed" if i == 0 else "refused"},
    )
    out = cr.evaluate(rows, "cand")
    # one rejected attempt per case, the other call is a refusal (not an attempt)
    assert out["rejection_of_attempts"]["value"] == 1.0
    assert not out["rejection_of_attempts"]["pass"]


def test_intervals_are_deterministic_and_ordered():
    rows = rows_for(
        20,
        lambda c, i: {"id_bad": int(c[1:]) % 4 == 0},
        lambda c, i: {},
    )
    first, second = cr.evaluate(rows, "cand"), cr.evaluate(rows, "cand")
    assert first == second
    lo, hi = first["id_noncompliance"]["ci"]
    assert lo <= first["id_noncompliance"]["diff"] <= hi


def test_summary_pools_calls_and_tokens():
    rows = rows_for(
        4,
        lambda c, i: {},
        lambda c, i: {"model_calls": 0 if i else 1, "prompt_tokens": 400},
    )
    s = cr.summary(rows)
    assert s["cand"]["model_calls_per_request"] == 0.5
    assert s["cand"]["prompt_tokens_per_request"] == 400
    assert s["original"]["requests"] == 8
