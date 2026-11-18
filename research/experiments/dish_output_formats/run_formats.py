# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
"""Run the answer formats of ``criteria.json`` on the 27 frozen inputs. Dry run by default;
``--allow-live-api`` makes the planned calls. The LangChain variants need the optional packages:

    uv run --project server --locked --with langchain-openai --with langchain-core \\
        python -m experiments.dish_output_formats.run_formats --allow-live-api

Results go to the ignored ``data/dish-formats/``.
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

from . import formats

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
RETRY_WAITS = (5, 15)
PACING_S = 1.0
FULL = ("S0", "S1", "S2", "S3", "S4")
CANDIDATES = ("S1", "S2", "S3", "S4")
HAS_HAVE = {"S0", "S2", "S4", "S5a", "S5b", "S2n", "S2r"}
HAS_MISSING = HAS_HAVE | {"S3"}


class CapReached(RuntimeError):
    pass


class Budget:
    def __init__(self, cap: int) -> None:
        self.cap, self.used = cap, 0

    def take(self) -> None:
        if self.used >= self.cap:
            raise CapReached("call cap reached")
        self.used += 1


def with_retry(send, budget: Budget, sleep=time.sleep) -> formats.Answer:
    """One logical call; HTTP 429 is repeated after 5 s and 15 s. Every attempt is counted."""
    attempts = 0
    while True:
        budget.take()
        attempts += 1
        answer = send()
        answer.attempts = attempts
        if answer.call.status != 429 or attempts > len(RETRY_WAITS):
            return answer
        sleep(RETRY_WAITS[attempts - 1])


def percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(q * (len(ordered) - 1)))]


def inputs_for(variant: str, cases: list[dict], criteria: dict) -> list[dict]:
    spec = criteria["variants"].get(variant, {})
    limit = spec.get("calls", len(cases))
    return cases[:limit]


def summarize(variant: str, rows: list[dict], results: list[dict], violations: dict) -> dict:
    calls = [r["call"] for r in rows]
    used = [c for c in calls if c["prompt_tokens"]]
    metrics = scoring.aggregate(results) if results else {}
    if variant not in HAS_HAVE:
        metrics["have_subset_share"] = None
    if variant not in HAS_MISSING:
        metrics["missing_disjoint_share"] = None
    final = [c for c in calls if c["status"] == 200]
    counts = [len(r["returned"]) for r in rows if r["ok"]]
    return {
        "inputs": len(rows),
        "metrics": metrics,
        "violations": violations,
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
        "mean_provider_cost_usd": (
            statistics.fmean(c["cost_usd"] for c in final)
            if final and all(c["cost_usd"] for c in final)
            else None
        ),
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


def qualifies(variant: str, s: dict, base: dict) -> dict:
    """The frozen rule's conditions for one candidate against S0 of the same day."""
    v, bm, m = s["violations"], base["metrics"], s["metrics"]
    kinds = ["names_outside_list"]
    if variant in HAS_HAVE:
        kinds.append("have_outside_owned")
    if variant in HAS_MISSING:
        kinds.append("missing_outside")
    checks = {
        "zero_violations": all(v[k] == 0 for k in kinds),
        "zero_truncated": s["truncated"] == 0,
        "zero_failed": s["failed"] == 0,
        "recall>=S0-0.02": (m.get("reference_recall") or 0)
        >= (bm.get("reference_recall") or 0) - 0.02,
        "precision>=S0-0.02": (m.get("reference_precision") or 0)
        >= (bm.get("reference_precision") or 0) - 0.02,
    }
    return {"checks": checks, "qualifies": all(checks.values())}


def decide(per_variant: dict[str, dict], lines: dict[str, int] | None = None) -> dict:
    """Apply the frozen rule to S1-S4 (S0 is the baseline); the cheapest qualifier wins."""
    base = per_variant["S0"]
    verdicts = {v: qualifies(v, per_variant[v], base) for v in CANDIDATES if v in per_variant}
    passing = [v for v, x in verdicts.items() if x["qualifies"]]
    code = {
        "S1": "raw_response_format",
        "S2": "raw_response_format",
        "S3": "raw_response_format",
        "S4": "raw_tools",
    }

    def key(v: str) -> tuple:
        return (per_variant[v]["mean_cost_usd"], (lines or {}).get(code[v], 0), v)

    passing.sort(key=key)
    chosen = None
    if passing:
        chosen = passing[0]
        for other in passing[1:]:
            near = (
                per_variant[other]["mean_cost_usd"] <= per_variant[chosen]["mean_cost_usd"] * 1.02
            )
            if near and (lines or {}).get(code[other], 0) < (lines or {}).get(code[chosen], 0):
                chosen = other
    return {"verdicts": verdicts, "qualifying": passing, "chosen": chosen}


def run_variant(variant, cases, ctx, key, budget, chain_factory=None, sleep=time.sleep) -> dict:
    catalog, service, names, vocab = ctx
    rows, results = [], []
    totals: dict[str, int] = {}
    for n, case in enumerate(cases):
        ingredients = case["ingredients"]
        if n:
            sleep(PACING_S)
        try:
            if variant in ("S5a", "S5b"):
                chain = chain_factory(variant, names, ingredients, vocab, key)
                answer = with_retry(
                    lambda c=chain, i=ingredients: formats.invoke_langchain(c, variant, i, names),
                    budget,
                    sleep,
                )
            else:
                build = (
                    formats.tools_payload if variant == "S4" else formats.response_format_payload
                )
                if variant == "S0":
                    payload = {
                        "model": formats.MODEL,
                        "messages": formats.messages_for("S0", ingredients, names),
                        "response_format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "dish_choice",
                                "strict": True,
                                "schema": formats.schema_for("S0", names, [], vocab),
                            },
                        },
                        "provider": {"require_parameters": True},
                        "max_tokens": formats.MAX_TOKENS,
                        "temperature": 0,
                    }
                else:
                    payload = build(variant, ingredients, names, vocab)
                answer = with_retry(lambda p=payload: formats.post_chat(p, key), budget, sleep)
        except CapReached:
            break
        call = answer.call
        data = formats.service_data(variant, call.data) if call.data is not None else None
        v = formats.count_violations(variant, call.data, ingredients, names, vocab)
        for k, x in v.items():
            totals[k] = totals.get(k, 0) + x
        dishes = (
            [d.model_dump() for d in check_suggest(data, service.catalog, service.recipes)]
            if data
            else []
        )
        raw_names = (
            [d["name"] for d in data["dishes"] if isinstance(d.get("name"), str)] if data else []
        )
        if variant not in HAS_HAVE:
            for d in dishes:
                d["have"] = []
        if variant not in HAS_MISSING:
            for d in dishes:
                d["missing"] = []
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
        rows.append(
            {
                "id": case["id"],
                "ok": call.ok,
                "error": call.error,
                "attempts": answer.attempts,
                "provider": answer.provider,
                "returned": [{k: d[k] for k in ("name", "have", "missing")} for d in dishes],
                "raw_answer": answer.raw,
                "violations": v,
                "call": call.__dict__ | {"data": None},
            }
        )
    out = summarize(variant, rows, results, totals)
    out["not_run"] = len(cases) - len(rows)
    return out


def rules_assisted(rows_s1: list[dict], cases: list[dict], catalog: Catalog) -> dict:
    """S6 from the stored S1 answers: model names, have/missing from the key ingredients."""
    results = []
    for row, case in zip(rows_s1, cases, strict=False):
        names_only = {"dishes": [r["name"] for r in row["returned"]]}
        dishes = formats.rules_assisted(catalog, names_only, case["ingredients"])
        results.append(
            scoring.case_result(
                [r["name"] for r in row["returned"]],
                dishes,
                case["ingredients"],
                {d.name for d in catalog.dishes.values()},
                reference(catalog, case["ingredients"]),
                missing_counts(catalog, case["ingredients"]),
                catalog.staples,
            )
        )
    return {"metrics": scoring.aggregate(results) if results else {}, "inputs": len(results)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live-api", action="store_true")
    parser.add_argument("--variants", default=",".join(formats.load_criteria()["run_order"]))
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "dish-formats")
    args = parser.parse_args(argv)
    criteria = formats.load_criteria()
    cases = formats.frozen_cases()
    variants = args.variants.split(",")
    plan = {v: len(inputs_for(v, cases, criteria)) for v in variants}
    print("plan", plan, "total", sum(plan.values()), "cap", criteria["call_cap"])
    if sum(plan.values()) > criteria["call_cap"]:
        print("over the call cap", file=sys.stderr)
        return 2
    if not args.allow_live_api:
        print("dry run: no model call (use --allow-live-api)")
        return 0
    key = read_key()
    if not key:
        print("no OPENROUTER_API_KEY", file=sys.stderr)
        return 2
    catalog = Catalog.load()
    service = DishService(catalog)
    names, vocab = formats.dish_names(catalog), formats.ingredient_vocabulary(catalog)
    ctx = (catalog, service, names, vocab)
    budget = Budget(criteria["call_cap"])
    per_variant: dict[str, dict] = {}
    for variant in variants:
        subset = inputs_for(variant, cases, criteria)
        try:
            per_variant[variant] = run_variant(
                variant, subset, ctx, key, budget, formats.langchain_structured
            )
        except ImportError as exc:
            per_variant[variant] = {"not_run": len(subset), "error": f"missing package: {exc.name}"}
            print(variant, "not run:", exc)
            continue
        s = per_variant[variant]
        print(
            variant,
            {
                k: (round(x, 4) if isinstance(x, float) else x)
                for k, x in s.items()
                if k not in ("rows", "metrics", "violations")
            },
            s.get("violations"),
        )
    summary = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        "vocabulary_size": len(vocab),
        "dish_names": len(names),
        "client_code_lines": formats.client_code_lines(),
        "variants": per_variant,
        "attempts_total": budget.used,
    }
    if "S0" in per_variant and "metrics" in per_variant["S0"]:
        summary["decision"] = decide(
            {v: s for v, s in per_variant.items() if "metrics" in s}, summary["client_code_lines"]
        )
    if "S1" in per_variant and "rows" in per_variant["S1"]:
        summary["S6_rules_assisted"] = rules_assisted(per_variant["S1"]["rows"], cases, catalog)
    summary["total_cost_usd"] = sum(
        s["mean_cost_usd"] * s["inputs"] for s in per_variant.values() if s.get("mean_cost_usd")
    )
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"formats-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("decision", json.dumps(summary.get("decision"), ensure_ascii=False))
    print("cost", round(summary["total_cost_usd"], 4), "wrote", path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
