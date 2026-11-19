# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Run round 5 of the answer-format study (spelling and list limit). Dry run by default;
``--allow-live-api`` makes the planned calls. Results go to the ignored
``data/dish-formats/round5.json``. Descriptive numbers only: no threshold decides anything."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from experiments.dish_naive import scoring
from experiments.dish_naive.run_naive import reference
from experiments.dish_tokens.calls import read_key

from app.dishes.answers import check_suggest, fewest_missing_first, salvage_list
from app.dishes.catalog import Catalog
from app.dishes.choices import ingredient_vocabulary, owned_vocabulary

from . import formats, round5
from .run_formats import Budget, CapReached, percentile, with_retry
from .run_round2 import paired_bootstrap
from .run_round4 import dist, round4_rules, shares, top5_share

REPO_ROOT = Path(__file__).resolve().parents[3]
PACING_S = 1.0


def one_call(
    case_id,
    ingredients,
    k,
    ctx,
    key,
    budget,
    send=formats.post_chat,
    sleep=time.sleep,
    in_schema=True,
    max_tokens=formats.MAX_TOKENS,
):
    catalog, vocab = ctx
    choices, payload = round5.body(catalog, vocab, ingredients, k, in_schema, max_tokens)
    answer = with_retry(lambda: send(payload, key), budget, sleep)
    call = answer.call
    data = call.data
    truncated = call.finish_reason == "length"
    if truncated:
        data = salvage_list(answer.raw)
    raw = (data or {}).get("dishes") if isinstance(data, dict) else None
    raw_count = len(raw) if isinstance(raw, list) else 0
    dishes = (
        fewest_missing_first(check_suggest(data, catalog, None, choices))
        if data is not None
        else []
    )
    rules = round4_rules(catalog, ingredients)
    owned = owned_vocabulary(list(ingredients), vocab)
    ref = reference(catalog, ingredients)
    case = scoring.case_result(
        [
            i.get("name")
            for i in raw or []
            if isinstance(i, dict) and isinstance(i.get("name"), str)
        ],
        [d.model_dump() for d in dishes],
        ingredients,
        {d.name for d in catalog.all()},
        ref,
        rules,
        catalog.staples,
    )
    return {
        "id": case_id,
        "ingredients": ingredients,
        "k": k,
        "answered": data is not None,
        "truncated": truncated,
        "raw_count": raw_count,
        "exceeded_k": k is not None and raw_count > k,
        "retries": answer.attempts - 1,
        "latency_s": call.latency_s,
        "status": call.status,
        "input_tokens": call.prompt_tokens,
        "output_tokens": call.completion_tokens,
        "cost": call.cost_usd or formats.token_cost(call.prompt_tokens, call.completion_tokens),
        "returned": [
            {"id": d.id, "missing": d.missing, "rules_missing": rules.get(d.id)} for d in dishes
        ],
        "owned_as_missing": sum(1 for d in dishes if owned & set(d.missing)),
        "reference_ids": sorted(ref),
        "case": case,
    }


def cut(row: dict, k: int) -> dict:
    """B_after_K: the server's ordered answer cut to the first k dishes (no call)."""
    out = dict(row, returned=row["returned"][:k], k=k)
    ids = {d["id"] for d in out["returned"]}
    out["case"] = dict(
        row["case"], dishes=len(ids), reference_hits=len(ids & set(row["reference_ids"]))
    )
    return out


def summarize(rows: list[dict]) -> dict:
    answered = [r for r in rows if r["answered"]]
    per_dish = [d for r in answered for d in r["returned"]]
    top = [s for s in (top5_share(r) for r in answered) if s is not None]
    return {
        "calls": len(rows),
        "cut_answers": sum(r["truncated"] for r in rows),
        "failed": sum(not r["answered"] for r in rows),
        "exceeded_k": sum(r["exceeded_k"] for r in rows),
        "retries_after_429": sum(r["retries"] for r in rows),
        "dishes_returned": dist([len(r["returned"]) for r in answered]),
        "rules_missing_shares": shares([d["rules_missing"] for d in per_dish]),
        "rules_missing_mean": round(statistics.fmean(d["rules_missing"] for d in per_dish), 2)
        if per_dish
        else None,
        "top5_le1_share_mean": round(statistics.fmean(top), 3) if top else None,
        "owned_as_missing_dishes": sum(r["owned_as_missing"] for r in rows),
        "reference": {
            k: v
            for k, v in scoring.aggregate([r["case"] for r in answered]).items()
            if k.startswith("reference_r") or k == "reference_precision"
        }
        if answered
        else {},
        "latency_p50": percentile([r["latency_s"] or 0 for r in rows], 0.5),
        "latency_p95": percentile([r["latency_s"] or 0 for r in rows], 0.95),
        "latency_max": max((r["latency_s"] or 0 for r in rows), default=None),
        "output_tokens": dist([r["output_tokens"] for r in rows]),
        "cost_total": sum(r["cost"] for r in rows),
    }


def metric(rows: list[dict], name: str) -> float | None:
    vals = []
    for r in rows:
        if not r["answered"]:
            continue
        n = len(r["returned"])
        if name == "dishes":
            vals.append(n)
        elif name == "rules_missing_mean" and n:
            vals.append(statistics.fmean(d["rules_missing"] for d in r["returned"]))
        elif name == "top5":
            s = top5_share(r)
            if s is not None:
                vals.append(s)
        elif name == "latency" and "latency_s" in r and r["latency_s"] is not None:
            vals.append(r["latency_s"])
        elif name == "output_tokens":
            vals.append(r["output_tokens"])
    return statistics.fmean(vals) if vals else None


def by_input(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r["id"], []).append(r)
    return out


def paired(base: list[dict], other: list[dict], metrics: tuple[str, ...]) -> dict:
    a, b = by_input(base), by_input(other)
    out = {}
    for m in metrics:
        diffs = []
        for cid in b:
            x, y = metric(b[cid], m), metric(a.get(cid, []), m)
            if x is not None and y is not None:
                diffs.append(x - y)
        out[m] = paired_bootstrap(diffs)
    return out


def overlap(capped: list[dict], after: list[dict]) -> dict:
    """Mean Jaccard overlap of dish sets and rules-missing difference, per input, cap vs cut."""
    a, b = by_input(after), by_input(capped)
    jac, diff = [], []
    for cid, rows in b.items():
        for r in rows:
            for s in a.get(cid, []):
                x = {d["id"] for d in r["returned"]}
                y = {d["id"] for d in s["returned"]}
                if x | y:
                    jac.append(len(x & y) / len(x | y))
        mx, my = metric(rows, "rules_missing_mean"), metric(a.get(cid, []), "rules_missing_mean")
        if mx is not None and my is not None:
            diff.append(mx - my)
    return {
        "jaccard_mean": round(statistics.fmean(jac), 3) if jac else None,
        "rules_missing_cap_minus_cut": paired_bootstrap(diff),
    }


def plan(
    crit: dict, cases: list[dict], limits: dict
) -> list[tuple[str, str, list[str], int | None]]:
    calls = []
    for rep in range(crit["part_a"]["repeats"]):
        for pair in crit["part_a"]["pairs"]:
            for side in ("a", "b"):
                calls.append((f"A{rep}", f"{pair['id']}{side}", pair[side], None))
    for rep in range(crit["part_b"]["repeats"]):
        for variant, k in (
            ("B_served", None),
            ("B_cap_mid", limits["K_mid"]),
            ("B_cap_high", limits["K_high"]),
        ):
            for c in cases:
                calls.append((f"{variant}#{rep}", c["id"], c["ingredients"], k))
    return calls


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--allow-live-api", action="store_true")
    p.add_argument("--out", type=Path, default=REPO_ROOT / "data/dish-formats/round5.json")
    args = p.parse_args(argv)
    crit = round5.criteria()
    catalog = Catalog.load()
    vocab = ingredient_vocabulary(catalog.all())
    cases = round5.demo_cases() + [dict(c) for c in formats.frozen_cases()]
    limits = round5.limit_values(catalog, cases)
    calls = plan(crit, cases, limits)
    print(
        f"{len(cases)} part-B inputs, limits {limits['K_mid']} / {limits['K_high']}, "
        f"{len(calls)} planned calls"
    )
    if not args.allow_live_api:
        return 0
    key = read_key()
    budget = Budget(crit["budget"]["model_calls"])
    rows: dict[str, list[dict]] = {}
    try:
        for n, (group, cid, ingredients, k) in enumerate(calls):
            if n:
                time.sleep(PACING_S)
            row = one_call(cid, ingredients, k, (catalog, vocab), key, budget)
            rows.setdefault(group.split("#")[0] if group.startswith("B") else "A", []).append(
                row | {"run": group}
            )
            print(n, group, cid, len(row["returned"]), row["latency_s"], file=sys.stderr)
    except CapReached:
        print("call cap reached", file=sys.stderr)
    served = rows.get("B_served", [])
    after = {
        name: [cut(r, limits[key_]) for r in served]
        for name, key_ in (("B_after_mid", "K_mid"), ("B_after_high", "K_high"))
    }
    variants = {k: v for k, v in rows.items() if k != "A"} | after
    metrics = ("dishes", "rules_missing_mean", "top5", "latency", "output_tokens")
    result = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "catalog_size": len(catalog),
        "limits": limits,
        "calls_attempted": budget.used,
        "part_a": rows.get("A", []),
        "summary": {v: summarize(r) for v, r in variants.items()},
        "paired_vs_served": {
            v: paired(served, r, metrics) for v, r in variants.items() if v != "B_served"
        },
        "cap_vs_cut": {
            "mid": overlap(rows.get("B_cap_mid", []), after["B_after_mid"]),
            "high": overlap(rows.get("B_cap_high", []), after["B_after_high"]),
        },
        "runs": {v: r for v, r in rows.items() if v != "A"},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
