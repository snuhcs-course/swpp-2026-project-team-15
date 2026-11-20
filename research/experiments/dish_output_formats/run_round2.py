# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Run round 2 of the answer-format study: R0, R1, R2 on the 27 frozen inputs and the mapping set.
Dry run by default; ``--allow-live-api`` makes the planned calls. Results go to the ignored
``data/dish-formats/``. Descriptive numbers only: no threshold decides anything.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from experiments.dish_naive import scoring
from experiments.dish_naive.run_naive import missing_counts, reference
from experiments.dish_tokens.calls import read_key

from app.dishes.answers import check_suggest
from app.dishes.catalog import Catalog
from app.dishes.service import DishService

from . import formats, round2
from .run_formats import Budget, CapReached, percentile, with_retry

REPO_ROOT = Path(__file__).resolve().parents[3]
PACING_S = 1.0
FIRST_15 = 15


def plan(criteria: dict, cases: list[dict], lists: list[dict]) -> list[tuple[str, str, list[dict]]]:
    first = lists[:FIRST_15]
    return [
        ("R0", "frozen", cases),
        ("R1", "frozen", cases),
        ("R2", "frozen", cases),
        ("R2", "mapping", lists),
        ("R1", "mapping", first),
        ("R0", "mapping", first),
    ]


def run_set(variant, kind, cases, ctx, key, budget, sleep=time.sleep, send=formats.post_chat):
    catalog, service, names, vocab = ctx
    rows, results = [], []
    totals: dict[str, int] = {}
    tally = dict.fromkeys(
        (
            "dishes",
            "owned_as_missing",
            "removals",
            "wrongly_hidden",
            "items",
            "correct",
            "false_merge",
            "missed_merge",
            "wrong_target",
            "ambiguous",
        ),
        0,
    )
    for n, case in enumerate(cases):
        ingredients = case["ingredients"]
        if n:
            sleep(PACING_S)
        unmatched = round2.unmatched_items(ingredients, vocab)
        request_enum = vocab if variant == "R0" else round2.missing_enum(ingredients, vocab)
        body = round2.payload(variant, ingredients, names, vocab)
        try:
            answer = with_retry(lambda p=body: send(p, key), budget, sleep)
        except CapReached:
            break
        call = answer.call
        data = call.data
        mapping = round2.read_mapping(data, unmatched, vocab) if variant == "R2" else {}
        cleaned, removed_n, removed = (
            round2.remove_mapped(data, mapping) if variant == "R2" else (data, 0, [])
        )
        v = round2.count_violations(data, ingredients, names, vocab, request_enum, unmatched)
        for k, x in v.items():
            totals[k] = totals.get(k, 0) + x
        service_in = formats.service_data("S2", cleaned) if cleaned is not None else None
        dishes = (
            [d.model_dump() for d in check_suggest(service_in, service.catalog, service.recipes)]
            if service_in
            else []
        )
        tally["dishes"] += len(dishes)
        tally["removals"] += removed_n
        row = {
            "id": case["id"],
            "ok": call.ok,
            "error": call.error,
            "attempts": answer.attempts,
            "provider": answer.provider,
            "unmatched": unmatched,
            "mapping": mapping,
            "removed": removed,
            "returned": [{k: d[k] for k in ("name", "have", "missing")} for d in dishes],
            "violations": v,
            "raw_answer": answer.raw,
            "call": call.__dict__ | {"data": None},
        }
        if kind == "frozen":
            raw_names = (
                [d["name"] for d in service_in["dishes"] if isinstance(d.get("name"), str)]
                if service_in
                else []
            )
            results.append(
                scoring.case_result(
                    raw_names,
                    dishes,
                    ingredients,
                    set(names),
                    reference(catalog, ingredients),
                    missing_counts(catalog, ingredients),
                    catalog.staples,
                )
            )
            row["case"] = results[-1]
        else:
            truly = round2.expected_owned_vocab(case, vocab)
            listed = round2.owned_listed_as_missing(dishes, truly)
            tally["owned_as_missing"] += listed
            tally["wrongly_hidden"] += round2.wrongly_hidden(removed, truly)
            if variant == "R2":
                for k, x in round2.score_mapping(case, mapping).items():
                    tally[k] += x
            row["owned_as_missing"] = listed
        rows.append(row)
    out = summarize(rows, results, totals, tally, kind)
    out["not_run"] = len(cases) - len(rows)
    return out


def summarize(rows, results, violations, tally, kind) -> dict:
    calls = [r["call"] for r in rows]
    used = [c for c in calls if c["prompt_tokens"]]
    metrics = scoring.aggregate(results) if results else {}
    counts = [len(r["returned"]) for r in rows if r["ok"]]
    out = {
        "kind": kind,
        "inputs": len(rows),
        "metrics": metrics,
        "violations": violations,
        "tally": tally,
        "truncated": sum(1 for c in calls if c["finish_reason"] == "length"),
        "failed": sum(1 for r in rows if not r["ok"] and r["call"]["finish_reason"] != "length"),
        "attempts": sum(r["attempts"] for r in rows),
        "mean_input": statistics.fmean(c["prompt_tokens"] for c in used) if used else None,
        "mean_output": statistics.fmean(c["completion_tokens"] for c in used) if used else None,
        "mean_cost_usd": statistics.fmean(
            formats.token_cost(c["prompt_tokens"], c["completion_tokens"]) for c in used
        )
        if used
        else None,
        "latency_median_s": statistics.median(c["latency_s"] for c in calls) if calls else None,
        "latency_p95_s": percentile([c["latency_s"] for c in calls], 0.95),
        "providers": sorted({r["provider"] for r in rows if r["provider"]}),
        "dishes_returned": {
            "min": min(counts, default=None),
            "median": statistics.median(counts) if counts else None,
            "max": max(counts, default=None),
        },
        "rows": rows,
    }
    if kind == "frozen" and metrics.get("missing_disjoint_share") is not None:
        out["owned_listed_as_missing_share"] = 1 - metrics["missing_disjoint_share"]
    elif tally["dishes"]:
        out["owned_listed_as_missing_share"] = tally["owned_as_missing"] / tally["dishes"]
    return out


BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 20261119


def case_metrics(row: dict, kind: str) -> dict[str, float | None]:
    """Per-input numbers used for the paired comparisons (None where undefined)."""
    dishes = len(row["returned"])
    out: dict[str, float | None] = {
        "dishes": float(dishes) if row["ok"] else None,
        "cost": formats.token_cost(row["call"]["prompt_tokens"], row["call"]["completion_tokens"])
        if row["call"]["prompt_tokens"]
        else None,
        "latency": row["call"]["latency_s"],
    }
    if not row["ok"]:
        return out | {"owned_as_missing": None, "recall": None, "precision": None}
    if kind == "frozen":
        case = row["case"]
        owned_as_missing = (dishes - case["missing_ok"]) / dishes if dishes else None
        out["owned_as_missing"] = owned_as_missing
        size = case["reference_size"]
        out["recall"] = case["reference_hits"] / size if size else None
        out["precision"] = case["reference_hits"] / dishes if dishes else None
    else:
        out["owned_as_missing"] = row["owned_as_missing"] / dishes if dishes else None
        out["recall"] = out["precision"] = None
    return out


def paired_bootstrap(diffs: list[float], seed: int = BOOTSTRAP_SEED) -> dict:
    """Mean paired difference with a percentile bootstrap 95% interval over the inputs."""
    import random

    if not diffs:
        return {"n": 0, "mean": None, "low": None, "high": None}
    rng = random.Random(seed)
    means = sorted(
        statistics.fmean(rng.choices(diffs, k=len(diffs))) for _ in range(BOOTSTRAP_RESAMPLES)
    )
    return {
        "n": len(diffs),
        "mean": statistics.fmean(diffs),
        "low": means[int(0.025 * (BOOTSTRAP_RESAMPLES - 1))],
        "high": means[int(0.975 * (BOOTSTRAP_RESAMPLES - 1))],
    }


def paired(a: dict, b: dict, kind: str) -> dict:
    """``a`` minus ``b`` per input for the inputs both variants answered."""
    by_id = {r["id"]: case_metrics(r, kind) for r in b["rows"]}
    out: dict[str, dict] = {}
    for metric in ("owned_as_missing", "dishes", "recall", "precision", "cost", "latency"):
        diffs = []
        for row in a["rows"]:
            x, y = case_metrics(row, kind)[metric], by_id.get(row["id"], {}).get(metric)
            if x is not None and y is not None:
                diffs.append(x - y)
        out[metric] = paired_bootstrap(diffs)
    return out


def mapping_table(run: dict, lists: list[dict]) -> list[dict]:
    """Every unmatched item with its label and what the model said (R2 on the mapping set)."""
    labels = {case["id"]: case for case in lists}
    table = []
    for row in run["rows"]:
        case = labels[row["id"]]
        for item, label in case["expected"].items():
            table.append(
                {
                    "list": row["id"],
                    "item": item,
                    "label": label,
                    "model": row["mapping"].get(item, "(omitted)") if row["ok"] else "(no answer)",
                    "ambiguous": item in case.get("ambiguous", []),
                }
            )
    return table


def owned_missing_count(row: dict) -> int:
    if "owned_as_missing" in row:
        return row["owned_as_missing"]
    case = row.get("case")
    return len(row["returned"]) - case["missing_ok"] if case else 0


def analysis(per: dict, lists: list[dict]) -> dict:
    """Descriptive numbers only: paired differences with intervals, the mapping table, examples."""
    out: dict = {"paired_frozen": {}, "paired_mapping_first15": {}}
    for a, b in (("R1", "R0"), ("R2", "R0"), ("R2", "R1")):
        if f"{a} frozen" in per and f"{b} frozen" in per:
            out["paired_frozen"][f"{a}-{b}"] = paired(
                per[f"{a} frozen"], per[f"{b} frozen"], "frozen"
            )
        if f"{a} mapping" in per and f"{b} mapping" in per:
            out["paired_mapping_first15"][f"{a}-{b}"] = paired(
                per[f"{a} mapping"], per[f"{b} mapping"], "mapping"
            )
    if "R2 mapping" in per:
        out["mapping_table"] = mapping_table(per["R2 mapping"], lists)
        out["wrongly_hidden"] = [
            {"list": r["id"], "removed": r["removed"], "mapping": r["mapping"]}
            for r in per["R2 mapping"]["rows"]
            if r["removed"]
        ]
    out["owned_as_missing_examples"] = {
        label: [
            {"id": r["id"], "returned": r["returned"][:3]}
            for r in run["rows"]
            if owned_missing_count(r)
        ][:3]
        for label, run in per.items()
    }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live-api", action="store_true")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "dish-formats")
    args = parser.parse_args(argv)
    criteria = round2.criteria()
    cases, lists = formats.frozen_cases(), round2.mapping_set()
    steps = plan(criteria, cases, lists)
    total = sum(len(c) for _, _, c in steps)
    print("plan", [(v, k, len(c)) for v, k, c in steps], "total", total)
    if total != criteria["call_plan"]["planned_calls"] or total > criteria["call_plan"]["call_cap"]:
        print("plan differs from the frozen criteria", file=sys.stderr)
        return 2
    if not args.allow_live_api:
        print("dry run: no model call (use --allow-live-api)")
        return 0
    key = read_key()
    if not key:
        print("no OPENROUTER_API_KEY", file=sys.stderr)
        return 2
    catalog = Catalog.load()
    ctx = (
        catalog,
        DishService(catalog),
        formats.dish_names(catalog),
        formats.ingredient_vocabulary(catalog),
    )
    budget = Budget(criteria["call_plan"]["call_cap"])
    per: dict[str, dict] = {}
    for variant, kind, subset in steps:
        label = f"{variant} {kind}"
        per[label] = run_set(variant, kind, subset, ctx, key, budget)
        s = per[label]
        print(
            label,
            {
                k: (round(x, 4) if isinstance(x, float) else x)
                for k, x in s.items()
                if k not in ("rows", "metrics", "violations", "tally")
            },
            s["violations"],
            s["tally"],
        )
    summary = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        "vocabulary_size": len(ctx[3]),
        "runs": per,
        "attempts_total": budget.used,
    }
    summary["analysis"] = analysis(per, lists)
    summary["total_cost_usd"] = sum(
        s["mean_cost_usd"] * s["inputs"] for s in per.values() if s.get("mean_cost_usd")
    )
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"round2-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("cost", round(summary["total_cost_usd"], 4), "wrote", path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
