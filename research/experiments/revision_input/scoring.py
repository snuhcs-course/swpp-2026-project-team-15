# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""Score one stored call with the independent checkers.

A stored call is the dict that ``run_experiment`` writes: status, parsed result, token usage,
number of model calls and latency. Scoring is judged under the ``list`` seasoning policy: the
inventory, water and the assumed seasonings that the recipe itself contains are available.
"""

from . import checkers as ck

POLICY = "list"


def score_record(
    rec: dict, case: dict, recipe, names: dict, index, assumed_ids
) -> dict:
    """Flat row of per-call measurements used by ``criteria``."""
    allowed = ck.allowed_ids(recipe, case["inventory_ids"], POLICY, assumed_ids)
    expected, _ = ck.expected_verdict(recipe, allowed)
    usage = rec.get("usage") or {}
    row = {
        "arm": rec["arm"],
        "case_id": rec["case_id"],
        "rep": rec["rep"],
        "status": rec["status"],
        "stratum": case["stratum"],
        "expected": expected,
        "prompt_tokens": usage.get("prompt_tokens"),
        "completion_tokens": usage.get("completion_tokens"),
        "latency_s": rec.get("latency_s"),
        "model_calls": rec.get("model_calls") or 0,
        "cost": rec.get("cost"),
    }
    result = rec.get("result")
    if result:
        issues = ck.structure(result, recipe)["issues"]
        row["inconsistent"] = bool(issues)
        row["issues"] = issues
    if result and result["can_revise"]:
        ids = ck.id_level(result, allowed, names)
        prose = ck.step_level(result, recipe, allowed, index)
        safety = ck.safety(result, recipe, names)
        row["id_bad"] = bool(ids["violating_ids"])
        row["unknown_id"] = bool(ids["unknown_ids"])
        row["stale"] = bool(prose["stale_missing_terms"])
        row["novel"] = bool(prose["novel_terms"])
        row["safety_applicable"] = safety["applicable"]
        row["safety_retained"] = safety.get("retained")
    return row


def delivered_violation(row: dict) -> bool:
    """A delivered revision that an independent checker flags."""
    return bool(
        row["status"] == "revised"
        and (row["id_bad"] or row["unknown_id"] or row["stale"] or row["novel"])
    )
