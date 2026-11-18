# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Round 2 of the naive dish study: does defining `have` in the prompt (or restricting it by the
schema) remove the invented `have` items? Variants and the adoption rule are frozen in
``criteria_round2.json``. Dry run by default; ``--allow-live-api`` makes the planned calls.
Results go to the ignored ``data/dish-naive/``.
"""

from __future__ import annotations

import argparse
import copy
import json
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from experiments.dish_tokens.calls import Call, chat, json_schema_format, read_key

from app.dishes.catalog import Catalog
from app.dishes.prompts import SUGGEST_SCHEMA, SUGGEST_SYSTEM, suggest_user_message
from app.dishes.service import DishService

from . import scoring
from .run_naive import missing_counts, reference

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
MODEL = "google/gemini-2.5-flash-lite"
MAX_TOKENS = 4096
ADOPTABLE = ("P1", "P2")


def prompts() -> dict[str, str]:
    criteria = json.loads((HERE / "criteria_round2.json").read_text(encoding="utf-8"))
    variants = criteria["variants"]
    return {
        "P0": SUGGEST_SYSTEM,
        "P1": variants["P1"]["prompt"],
        "P2": variants["P2"]["prompt"],
        "P3": variants["P3"]["prompt"],
    }


def schema_for(variant: str, ingredients: list[str]) -> dict:
    schema = copy.deepcopy(SUGGEST_SCHEMA)
    item = schema["properties"]["dishes"]["items"]
    if variant == "P2":
        owned = list(dict.fromkeys(i.strip() for i in ingredients if i.strip()))
        item["properties"]["have"]["items"] = {"type": "string", "enum": owned}
    if variant == "P3":
        del item["properties"]["have"]
        item["required"] = ["name", "missing"]
    return schema


def payload_for(
    variant: str, ingredients: list[str], names: list[str], max_tokens: int = MAX_TOKENS
) -> dict:
    return {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": prompts()[variant]},
            {"role": "user", "content": suggest_user_message(ingredients, names)},
        ],
        "response_format": json_schema_format("dish_choice", schema_for(variant, ingredients)),
        "provider": {"require_parameters": True},
        "max_tokens": max_tokens,
        "temperature": 0,
    }


RETRY_WAITS = (5, 15)  # seconds before the second and third attempt after an HTTP 429
CALLS_MADE = {"n": 0}


def chat_with_retry(payload: dict, key: str, cap: int) -> tuple[Call, int]:
    """One logical call; repeated after HTTP 429 (provider rate limit). Returns (call, attempts)."""
    attempts = 0
    while True:
        if CALLS_MADE["n"] >= cap:
            raise RuntimeError("call cap reached")
        CALLS_MADE["n"] += 1
        attempts += 1
        call = chat(payload, key)
        if call.status != 429 or attempts > len(RETRY_WAITS):
            return call, attempts
        time.sleep(RETRY_WAITS[attempts - 1])


def decide(per_variant: dict[str, dict]) -> dict:
    """Apply the frozen adoption rule to the aggregated variants (P0 is the baseline)."""
    base = per_variant["P0"]["metrics"]
    verdicts: dict[str, dict] = {}
    for variant in ADOPTABLE:
        v = per_variant.get(variant)
        if v is None:
            continue
        m = v["metrics"]

        def ok(key: str, floor: float | None = None, _m: dict = m) -> bool:
            value = _m.get(key)
            if value is None or (floor is None and base.get(key) is None):
                return False
            return value >= (floor if floor is not None else base[key] - 0.02)

        checks = {
            "have_subset>=0.99": ok("have_subset_share", 0.99),
            "valid_names==1": ok("valid_names_share", 1.0),
            "nonempty": ok("nonempty_when_possible"),
            "recall": ok("reference_recall"),
            "precision": ok("reference_precision"),
            "no_truncation_or_failure": v["truncated"] == 0 and v["failed"] == 0,
        }
        verdicts[variant] = {"checks": checks, "adopt_ok": all(checks.values())}
    passing = [v for v in ADOPTABLE if verdicts.get(v, {}).get("adopt_ok")]
    passing.sort(key=lambda v: (per_variant[v]["mean_cost_usd"], v))
    return {"verdicts": verdicts, "adopted": passing[0] if passing else None}


def run_variant(
    variant, cases, names, name_set, catalog, service, key, cap, max_tokens=MAX_TOKENS
) -> dict:
    rows, results = [], []
    for case in cases:
        ingredients = case["ingredients"]
        call, attempts = chat_with_retry(
            payload_for(variant, ingredients, names, max_tokens), key, cap
        )
        dishes, raw_names, returned = [], [], []
        if call.data is not None:
            items = call.data.get("dishes")
            raw_names = (
                [d["name"] for d in items if isinstance(d, dict) and isinstance(d.get("name"), str)]
                if isinstance(items, list)
                else []
            )
            dishes = [d.model_dump() for d in service.check_suggest(call.data)]
            returned = [{k: d[k] for k in ("name", "have", "missing")} for d in dishes]
        if variant == "P3":  # no `have` by construction: score it as empty so it cannot fail it
            for d in dishes:
                d["have"] = []
        results.append(
            scoring.case_result(
                raw_names,
                dishes,
                ingredients,
                name_set,
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
                "attempts": attempts,
                "returned": returned,
                "call": call.__dict__,
            }
        )
    calls = [r["call"] for r in rows]
    metrics = scoring.aggregate(results)
    if variant == "P3":
        metrics["have_subset_share"] = None
    return {
        "metrics": metrics,
        "calls": len(calls),
        "failed": sum(1 for r in rows if not r["ok"]),
        "truncated": sum(1 for c in calls if c["finish_reason"] == "length"),
        "mean_input": statistics.fmean(c["prompt_tokens"] for c in calls),
        "mean_output": statistics.fmean(c["completion_tokens"] for c in calls),
        "mean_cost_usd": statistics.fmean(c["cost_usd"] for c in calls),
        "median_latency_s": statistics.median(c["latency_s"] for c in calls),
        "rows": rows,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live-api", action="store_true")
    parser.add_argument("--variants", default="P0,P1,P2,P3")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "dish-naive")
    args = parser.parse_args(argv)
    criteria = json.loads((HERE / "criteria_round2.json").read_text(encoding="utf-8"))
    naive = json.loads((HERE / "criteria.json").read_text(encoding="utf-8"))
    cases = [c for c in naive["cases"] if c["expect_status"] == 200]
    variants = args.variants.split(",")
    total = len(cases) * len(variants)
    cap = criteria["call_cap"] - criteria.get("calls_already_made", 0)
    print(f"{len(cases)} inputs x {len(variants)} variants = {total} calls (cap {cap} left)")
    if total > cap:
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
    names = list(service._by_name)  # noqa: SLF001
    per_variant: dict[str, dict] = {}
    for variant in variants:
        per_variant[variant] = run_variant(
            variant, cases, names, set(names), catalog, service, key, cap
        )
        v = per_variant[variant]
        print(
            variant,
            {k: (round(x, 4) if isinstance(x, float) else x) for k, x in v.items() if k != "rows"},
        )
    summary = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        "decision": decide(per_variant) if "P0" in per_variant else None,
        "variants": per_variant,
        "total_calls": sum(v["calls"] for v in per_variant.values()),
        "attempts": CALLS_MADE["n"],
        "total_cost_usd": sum(v["mean_cost_usd"] * v["calls"] for v in per_variant.values()),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"round2-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("decision", json.dumps(summary["decision"], ensure_ascii=False))
    print("cost", round(summary["total_cost_usd"], 4), "wrote", path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
