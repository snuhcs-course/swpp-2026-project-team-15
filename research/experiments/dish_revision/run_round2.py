# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Round 2 runner: one model answer per case through the real server request, four variants.

``--build-real-cases PATH`` writes the fridges for the recipes made from captions (an untracked
file) without any call. ``--allow-live-api`` runs the frozen 36 synthetic cases and, with
``--real-recipes``, the real-recipe cases. Results go to the ignored ``data/dish-revision/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from experiments.dish_naive.run_naive import RecordingLLM, Usage, UsageTransport, git
from experiments.dish_tokens.calls import read_key

from app.dishes.catalog import Catalog
from app.dishes.llm import DEFAULT_MODEL, DishLLM, DishLLMError
from app.dishes.recipes import RecipeStore
from app.dishes.revision import Reviser

from . import round2, scoring

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
OUT = REPO_ROOT / "data" / "dish-revision"
CALL_CAP = 200
PRICE_PER_MTOK = (0.10, 0.40)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cost(row: dict) -> float:
    if row.get("cost") is not None:
        return float(row["cost"])
    p, c = row.get("prompt_tokens", 0), row.get("completion_tokens", 0)
    return (p * PRICE_PER_MTOK[0] + c * PRICE_PER_MTOK[1]) / 1e6


def run_set(name, cases, store, catalog, llm, usage) -> dict:
    per_variant: dict[str, list[dict]] = {v: [] for v in round2.VARIANTS}
    calls, coverage, mismatch, raws = [], [], [], {}
    for case in cases:
        if len(usage.rows) >= CALL_CAP:
            print("call cap reached; stopping", file=sys.stderr)
            break
        recipe = store.get(case["dish_id"])
        dish = catalog.get(case["dish_id"])
        reviser = Reviser(catalog, catalog, llm, store)
        status = reviser.availability(recipe, case["ingredients"])
        before = len(usage.rows)
        llm.last = None  # a case without a model call must not reuse the previous answer
        served = None
        try:
            served = reviser.revise(case["dish_id"], case["ingredients"]).status
        except DishLLMError as exc:
            print(f"{case['id']}: provider error {exc}", file=sys.stderr)
        raw = llm.last
        requests = usage.rows[before:]
        ok = [r for r in requests if r["status"] == 200]
        calls.append(
            {
                "id": case["id"],
                "requests": len(requests),
                "latency_s": ok[-1]["latency_s"] if ok else None,
                "cost_usd": sum(cost(r) for r in requests),
                "finish_reason": ok[-1].get("finish_reason") if ok else None,
            }
        )
        if raw and raw.get("can_revise") is True:
            coverage.append(
                {
                    "id": case["id"],
                    "ingredients": scoring.ingredient_coverage(recipe, raw),
                    "steps": scoring.step_coverage(recipe, raw),
                }
            )
        raws[case["id"]] = raw
        for variant in round2.VARIANTS:
            if not requests and served is not None:  # nothing unavailable: no call is needed
                out = {"status": served, "code": "no_call_needed", "call": False}
            else:
                out = round2.decide(
                    variant, raw, recipe, dish.name, status, catalog, case["ingredients"]
                )
            per_variant[variant].append({"id": case["id"], "expect": case["expect"], **out})
        if served is not None and per_variant["current"][-1]["status"] != served:
            mismatch.append(case["id"])
        print(case["id"], case["expect"], *(per_variant[v][-1]["status"] for v in round2.VARIANTS))
    summary = {v: round2.summarize(rows) for v, rows in per_variant.items()}
    return {
        "set": name,
        "rows": per_variant,
        "summary": summary,
        "transitions_current_to_both": round2.transitions(
            per_variant["current"], per_variant["both"]
        ),
        "calls": calls,
        "latency_cost": round2.latency_cost(calls),
        "coverage": coverage,
        "served_vs_current_mismatch": mismatch,
        "raw_answers": raws,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live-api", action="store_true")
    parser.add_argument("--real-recipes", type=Path, help="recipes file made from captions")
    parser.add_argument("--build-real-cases", type=Path, help="write the real-recipe fridges here")
    parser.add_argument("--real-only", action="store_true", help="skip the synthetic cases")
    args = parser.parse_args(argv)
    catalog = Catalog.load()
    if args.build_real_cases:
        real = RecipeStore.load(args.real_recipes)
        ids = json.loads(args.real_recipes.read_text(encoding="utf-8"))["recipes"]
        recipes = {d: real.get(d) for d in ids}
        cases = round2.build_real_cases(recipes, catalog)
        args.build_real_cases.parent.mkdir(parents=True, exist_ok=True)
        args.build_real_cases.write_text(
            json.dumps({"cases": cases}, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        print(f"{len(cases)} real-recipe cases -> {args.build_real_cases}")
        return 0
    synthetic = RecipeStore.load(HERE / "fixtures.json")
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["cases"]
    real_cases_path = OUT / "real-cases.json"
    plan = len(cases) + (
        len(json.loads(real_cases_path.read_text())["cases"]) if args.real_recipes else 0
    )
    print(f"plan: {plan} model calls (cap {CALL_CAP}), model {DEFAULT_MODEL}")
    if not args.allow_live_api:
        print("dry run: no model call (use --allow-live-api)")
        return 0
    key = read_key()
    if not key:
        print("no OpenRouter key found", file=sys.stderr)
        return 2
    usage = Usage()
    llm = RecordingLLM(DishLLM(key, DEFAULT_MODEL, transport=UsageTransport(usage)))
    results = (
        [] if args.real_only else [run_set("synthetic", cases, synthetic, catalog, llm, usage)]
    )
    if args.real_recipes:
        real = RecipeStore.load(args.real_recipes)
        real_cases = json.loads(real_cases_path.read_text(encoding="utf-8"))["cases"]
        results.append(run_set("real", real_cases, real, catalog, llm, usage))
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    OUT.mkdir(parents=True, exist_ok=True)
    report = {
        "date": stamp,
        "commit": git("rev-parse", "HEAD"),
        "model": DEFAULT_MODEL,
        "criteria_sha256": sha256(HERE / "criteria_round2.json"),
        "requests": len(usage.rows),
        "retried": sum(1 for r in usage.rows if r["status"] == 429),
        "results": results,
    }
    (OUT / f"round2-{stamp}.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps({r["set"]: r["summary"] for r in results}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
