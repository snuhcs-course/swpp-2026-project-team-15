# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Run round 3 of the answer-format study (list length). Dry run by default; ``--allow-live-api``
makes the planned calls. Results go to the ignored ``data/dish-formats/round3.json``.
Descriptive numbers only: no threshold decides anything."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from experiments.dish_naive import scoring
from experiments.dish_naive.run_naive import reference
from experiments.dish_tokens.calls import read_key

from app.dishes.answers import salvage_list
from app.dishes.catalog import Catalog
from app.dishes.choices import ingredient_vocabulary

from . import formats, round3
from .run_formats import Budget, CapReached, percentile, with_retry
from .run_round2 import paired_bootstrap

REPO_ROOT = Path(__file__).resolve().parents[3]
PACING_S = 1.0


def one_case(variant, case, ctx, key, budget, send=formats.post_chat, sleep=time.sleep):
    catalog, vocab = ctx
    ingredients = case["ingredients"]
    choices = round3.choices_for(catalog, vocab, ingredients)
    body = round3.payload(variant, choices)
    answer = with_retry(lambda: send(body, key), budget, sleep)
    call = answer.call
    data = call.data
    truncated = call.finish_reason == "length"
    if truncated:
        data = salvage_list(answer.raw)
    dishes = round3.checked(variant, data, catalog, choices)
    rules = round3.rules_missing(catalog, ingredients)
    names = {d.name for d in catalog.all()}
    raw_names = [d.get("name") for d in (data or {}).get("dishes", []) if isinstance(d, dict)]
    case_result = scoring.case_result(
        [n for n in raw_names if isinstance(n, str)],
        [d.model_dump() for d in dishes],
        ingredients,
        names,
        reference(catalog, ingredients),
        rules,
        catalog.staples,
    )
    fits = round3.fits_by_id(data, catalog) if variant == "PC" else {}
    return {
        "id": case["id"],
        "ingredients": ingredients,
        "answered": data is not None,
        "truncated": truncated,
        "error": None if data is not None else call.error,
        "attempts": answer.attempts,
        "returned": [
            {
                "id": d.id,
                "missing": d.missing,
                "rules_missing": rules.get(d.id),
                "fit": fits.get(d.id),
            }
            for d in dishes
        ],
        "owned_as_missing": round3.owned_listed_as_missing(dishes, ingredients, vocab),
        "case": case_result,
        "call": call.__dict__ | {"data": None},
    }


def dist(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "mean": round(statistics.fmean(values), 2),
        "max": max(values),
    }


def shares(counts: list[int]) -> dict:
    c = Counter(round3.bucket(n) for n in counts)
    total = sum(c.values())
    return {k: round(c.get(k, 0) / total, 3) if total else None for k in ("0", "1", "2", "3+")}


def summarize(rows: list[dict]) -> dict:
    answered = [r for r in rows if r["answered"]]
    per_dish = [d for r in answered for d in r["returned"]]
    calls = [r["call"] for r in rows]
    costs = [
        c["cost_usd"] or formats.token_cost(c["prompt_tokens"], c["completion_tokens"])
        for c in calls
    ]
    lat = [c["latency_s"] for c in calls if c.get("latency_s") is not None]
    out = {
        "inputs": len(rows),
        "answered": len(answered),
        "truncated": sum(r["truncated"] for r in rows),
        "failed": sum(not r["answered"] for r in rows),
        "dishes_returned": dist([len(r["returned"]) for r in answered]),
        "model_missing_per_dish": dist([len(d["missing"]) for d in per_dish]),
        "rules_missing_per_dish": dist([d["rules_missing"] for d in per_dish]),
        "model_missing_shares": shares([len(d["missing"]) for d in per_dish]),
        "rules_missing_shares": shares([d["rules_missing"] for d in per_dish]),
        "owned_as_missing_dishes": sum(r["owned_as_missing"] for r in rows),
        "reference": scoring.aggregate([r["case"] for r in answered]) if answered else {},
        "latency_p50": percentile(lat, 0.5),
        "latency_p95": percentile(lat, 0.95),
        "mean_input_tokens": statistics.fmean(c["prompt_tokens"] for c in calls) if calls else None,
        "mean_output_tokens": statistics.fmean(c["completion_tokens"] for c in calls)
        if calls
        else None,
        "cost_per_call": statistics.fmean(costs) if costs else None,
        "cost_total": sum(costs),
        "attempts": sum(r["attempts"] for r in rows),
    }
    fits = [d for d in per_dish if d["fit"]]
    if fits:
        by_fit: dict[str, list[int]] = {}
        for d in fits:
            by_fit.setdefault(d["fit"], []).append(d["rules_missing"])
        out["fit"] = {k: {"dishes": len(v), "rules_missing": dist(v)} for k, v in by_fit.items()}
    return out


def per_input(row: dict) -> dict[str, float | None]:
    if not row["answered"]:
        return dict.fromkeys(("dishes", "rules_missing_mean", "recall", "precision", "latency"))
    n = len(row["returned"])
    c = row["case"]
    return {
        "dishes": float(n),
        "rules_missing_mean": statistics.fmean(d["rules_missing"] for d in row["returned"])
        if n
        else None,
        "recall": c["reference_hits"] / c["reference_size"] if c["reference_size"] else None,
        "precision": c["reference_hits"] / n if n else None,
        "latency": row["call"]["latency_s"],
    }


def paired_vs(base: list[dict], other: list[dict]) -> dict:
    by_id = {r["id"]: per_input(r) for r in base}
    out = {}
    for metric in ("dishes", "rules_missing_mean", "recall", "precision", "latency"):
        diffs = []
        for r in other:
            x, y = per_input(r)[metric], by_id.get(r["id"], {}).get(metric)
            if x is not None and y is not None:
                diffs.append(x - y)
        out[metric] = paired_bootstrap(diffs)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--allow-live-api", action="store_true")
    p.add_argument("--out", type=Path, default=REPO_ROOT / "data/dish-formats/round3.json")
    args = p.parse_args(argv)
    crit = round3.criteria()
    cases = formats.frozen_cases()
    catalog = Catalog.load()
    vocab = ingredient_vocabulary(catalog.all())
    planned = len(cases) * len(round3.VARIANTS)
    print(f"{planned} planned calls over {len(round3.VARIANTS)} variants, catalog {len(catalog)}")
    if not args.allow_live_api:
        return 0
    key = read_key()
    budget = Budget(crit["budget"]["model_calls"])
    runs: dict[str, list[dict]] = {}
    try:
        for variant in round3.VARIANTS:
            runs[variant] = []
            for n, case in enumerate(cases):
                if n:
                    time.sleep(PACING_S)
                runs[variant].append(one_case(variant, case, (catalog, vocab), key, budget))
            print(variant, "done", file=sys.stderr)
    except CapReached:
        print("call cap reached", file=sys.stderr)
    result = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "catalog_size": len(catalog),
        "calls_attempted": budget.used,
        "summary": {v: summarize(rows) for v, rows in runs.items()},
        "paired_vs_P0": {v: paired_vs(runs["P0"], rows) for v, rows in runs.items() if v != "P0"},
        "runs": runs,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
