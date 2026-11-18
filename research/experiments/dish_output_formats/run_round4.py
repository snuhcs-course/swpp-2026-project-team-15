# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Run round 4 of the answer-format study (structure). Dry run by default; ``--allow-live-api``
makes the planned calls. Results go to the ignored ``data/dish-formats/round4.json``.
Descriptive numbers only: no threshold decides anything."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

from experiments.dish_naive import scoring
from experiments.dish_naive.run_naive import reference
from experiments.dish_tokens.calls import read_key

from app.dishes.answers import check_suggest, fewest_missing_first, salvage_list
from app.dishes.catalog import Catalog
from app.dishes.choices import ingredient_vocabulary, owned_vocabulary

from . import formats, round4
from .run_formats import Budget, CapReached, percentile, with_retry
from .run_round2 import paired_bootstrap

REPO_ROOT = Path(__file__).resolve().parents[3]
PACING_S = 1.0


class LockedBudget(Budget):
    def __init__(self, cap: int) -> None:
        super().__init__(cap)
        self._lock = threading.Lock()

    def take(self) -> None:
        with self._lock:
            super().take()


def one_request(req: round4.Request, key, budget, send=formats.post_chat, sleep=time.sleep):
    answer = with_retry(lambda: send(req.body, key), budget, sleep)
    call = answer.call
    data = call.data
    truncated = call.finish_reason == "length"
    if truncated:
        data = salvage_list(answer.raw)
    return {
        "group": req.group,
        "data": formats.service_data("S1", data) if data is not None else None,
        "truncated": truncated,
        "attempts": answer.attempts,
        "call": call.__dict__ | {"data": None},
    }


def run_case(variant, case, ctx, key, budget, send=formats.post_chat, sleep=time.sleep):
    catalog, vocab = ctx
    ingredients = case["ingredients"]
    reqs = round4.requests_for(variant, case["id"], ingredients, catalog, vocab)
    started = time.monotonic()
    if len(reqs) == 1:
        parts = [one_request(reqs[0], key, budget, send, sleep)]
    else:
        with ThreadPoolExecutor(max_workers=len(reqs)) as pool:
            parts = list(pool.map(lambda r: one_request(r, key, budget, send, sleep), reqs))
    wall = time.monotonic() - started
    dishes = []
    for req, part in zip(reqs, parts, strict=True):
        if part["data"] is not None:
            dishes += check_suggest(part["data"], catalog, None, req.choices)
    seen: set[str] = set()
    dishes = [d for d in dishes if not (d.id in seen or seen.add(d.id))]
    dishes = fewest_missing_first(dishes)
    rules = round4_rules(catalog, ingredients)
    owned = owned_vocabulary(list(ingredients), vocab)
    staples = round4.staple_forms(catalog.staples)
    raw_names = [
        item.get("name")
        for part in parts
        for item in ((part["data"] or {}).get("dishes") or [])
        if isinstance(item, dict)
    ]
    case_result = scoring.case_result(
        [n for n in raw_names if isinstance(n, str)],
        [d.model_dump() for d in dishes],
        ingredients,
        {d.name for d in catalog.all()},
        reference(catalog, ingredients),
        rules,
        catalog.staples,
    )
    answered = any(p["data"] is not None for p in parts)
    calls = [p["call"] for p in parts]
    return {
        "id": case["id"],
        "ingredients": ingredients,
        "answered": answered,
        "requests": len(parts),
        "truncated_calls": sum(p["truncated"] for p in parts),
        "failed_calls": sum(p["data"] is None for p in parts),
        "retries": sum(p["attempts"] - 1 for p in parts),
        "wall_s": wall,
        "slowest_s": max((c["latency_s"] or 0) for c in calls),
        "input_tokens": sum(c["prompt_tokens"] for c in calls),
        "output_tokens": sum(c["completion_tokens"] for c in calls),
        "cost": sum(
            c["cost_usd"] or formats.token_cost(c["prompt_tokens"], c["completion_tokens"])
            for c in calls
        ),
        "returned": [
            {"id": d.id, "missing": d.missing, "rules_missing": rules.get(d.id)} for d in dishes
        ],
        "owned_as_missing": sum(1 for d in dishes if owned & set(d.missing)),
        "staple_missing_items": sum(1 for d in dishes for m in d.missing if m in staples),
        "case": case_result,
        "groups": [
            {
                "group": p["group"],
                "truncated": p["truncated"],
                "ok": p["data"] is not None,
                "latency_s": p["call"]["latency_s"],
                "status": p["call"]["status"],
            }
            for p in parts
        ],
    }


def round4_rules(catalog: Catalog, ingredients: list[str]) -> dict[str, int]:
    owned = catalog.owned(ingredients)
    return {d.id: len(catalog.match(d, owned).missing) for d in catalog.all()}


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
    c = Counter(round4.bucket(n) for n in counts)
    total = sum(c.values())
    return {k: round(c.get(k, 0) / total, 3) if total else None for k in ("0", "1", "2", "3+")}


def top5_share(row: dict) -> float | None:
    top = row["returned"][:5]
    return sum(d["rules_missing"] <= 1 for d in top) / len(top) if top else None


def summarize(rows: list[dict]) -> dict:
    answered = [r for r in rows if r["answered"]]
    per_dish = [d for r in answered for d in r["returned"]]
    top = [s for s in (top5_share(r) for r in answered) if s is not None]
    missing_items = sum(len(d["missing"]) for d in per_dish)
    return {
        "inputs": len(rows),
        "requests": sum(r["requests"] for r in rows),
        "inputs_with_a_cut_call": sum(r["truncated_calls"] > 0 for r in rows),
        "truncated_calls": sum(r["truncated_calls"] for r in rows),
        "failed_calls": sum(r["failed_calls"] for r in rows),
        "retries_after_429": sum(r["retries"] for r in rows),
        "dishes_returned": dist([len(r["returned"]) for r in answered]),
        "model_missing_shares": shares([len(d["missing"]) for d in per_dish]),
        "rules_missing_shares": shares([d["rules_missing"] for d in per_dish]),
        "rules_missing_mean": round(statistics.fmean(d["rules_missing"] for d in per_dish), 2)
        if per_dish
        else None,
        "top5_le1_share_mean": round(statistics.fmean(top), 3) if top else None,
        "owned_as_missing_dishes": sum(r["owned_as_missing"] for r in rows),
        "staple_share_of_missing_items": round(
            sum(r["staple_missing_items"] for r in answered) / missing_items, 3
        )
        if missing_items
        else None,
        "reference": scoring.aggregate([r["case"] for r in answered]) if answered else {},
        "wall_p50": percentile([r["wall_s"] for r in rows], 0.5),
        "wall_p95": percentile([r["wall_s"] for r in rows], 0.95),
        "mean_input_tokens": statistics.fmean(r["input_tokens"] for r in rows) if rows else None,
        "mean_output_tokens": statistics.fmean(r["output_tokens"] for r in rows) if rows else None,
        "cost_per_input": statistics.fmean(r["cost"] for r in rows) if rows else None,
        "cost_total": sum(r["cost"] for r in rows),
    }


def per_input(row: dict) -> dict[str, float | None]:
    keys = ("dishes", "rules_missing_mean", "top5", "recall", "precision", "wall", "cost")
    if not row["answered"]:
        return dict.fromkeys(keys)
    n = len(row["returned"])
    c = row["case"]
    return {
        "dishes": float(n),
        "rules_missing_mean": statistics.fmean(d["rules_missing"] for d in row["returned"])
        if n
        else None,
        "top5": top5_share(row),
        "recall": c["reference_hits"] / c["reference_size"] if c["reference_size"] else None,
        "precision": c["reference_hits"] / n if n else None,
        "wall": row["wall_s"],
        "cost": row["cost"],
    }


def paired_vs(base: list[dict], other: list[dict]) -> dict:
    by_id = {r["id"]: per_input(r) for r in base}
    out = {}
    for metric in ("dishes", "rules_missing_mean", "top5", "recall", "precision", "wall", "cost"):
        diffs = []
        for r in other:
            x, y = per_input(r)[metric], by_id.get(r["id"], {}).get(metric)
            if x is not None and y is not None:
                diffs.append(x - y)
        out[metric] = paired_bootstrap(diffs)
    return out


def plan(cases: list[dict]) -> dict[str, list[dict]]:
    everyone = round4.demo_cases() + cases
    subset = round4.split_cases(cases)
    return {
        "S_now": everyone,
        "S_noseason": everyone,
        "S_shuffle": everyone,
        "S_names": subset,
        "S_split": subset,
        "S_split_noseason": subset,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--allow-live-api", action="store_true")
    p.add_argument("--out", type=Path, default=REPO_ROOT / "data/dish-formats/round4.json")
    args = p.parse_args(argv)
    crit = round4.criteria()
    catalog = Catalog.load()
    vocab = ingredient_vocabulary(catalog.all())
    runs_plan = plan(formats.frozen_cases())
    groups = len(round4.category_groups(catalog))
    planned = sum(
        len(cases) * (groups if v in round4.SPLIT else 1) for v, cases in runs_plan.items()
    )
    print(f"{planned} planned calls, catalog {len(catalog)} dishes in {groups} categories")
    if not args.allow_live_api:
        return 0
    key = read_key()
    budget = LockedBudget(crit["budget"]["model_calls"])
    runs: dict[str, list[dict]] = {}
    try:
        for variant, cases in runs_plan.items():
            runs[variant] = []
            for n, case in enumerate(cases):
                if n:
                    time.sleep(PACING_S)
                runs[variant].append(run_case(variant, case, (catalog, vocab), key, budget))
            print(variant, "done", file=sys.stderr)
    except CapReached:
        print("call cap reached", file=sys.stderr)
    result = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "catalog_size": len(catalog),
        "categories": groups,
        "calls_attempted": budget.used,
        "summary": {v: summarize(rows) for v, rows in runs.items()},
        "paired_vs_S_now": {
            v: paired_vs(runs["S_now"], rows) for v, rows in runs.items() if v != "S_now"
        },
        "runs": runs,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
