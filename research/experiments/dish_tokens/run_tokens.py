# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Run the frozen token-study variants on the naive selection call (see criteria.json).

Default is a dry run. ``--allow-live-api`` makes one model call per variant and input.
Results go to the ignored ``data/dish-tokens/`` directory.
"""

from __future__ import annotations

import argparse
import copy
import json
import statistics
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from experiments.dish_naive import scoring
from experiments.dish_naive.run_naive import missing_counts, reference
from experiments.legacy_prompts import SUGGEST_SCHEMA, SUGGEST_SYSTEM

from app.dishes.answers import check_suggest
from app.dishes.catalog import Catalog
from app.dishes.prompts import suggest_user_message
from app.dishes.service import DishService

from .calls import Call, chat, json_schema_format, read_key

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
MODEL = "google/gemini-2.5-flash-lite"
CEILING = 8192
MINIMAL_SCHEMA = copy.deepcopy(SUGGEST_SCHEMA)
_item = MINIMAL_SCHEMA["properties"]["dishes"]["items"]
del _item["properties"]["have"]
_item["required"] = ["name", "missing"]


def user_message(variant: str, ingredients: list[str], names: list[str]) -> str:
    if variant == "V2":
        return "owned: " + ", ".join(ingredients) + "\ndishes: " + ", ".join(names)
    if variant == "V5":
        return json.dumps({"dishes": names, "owned": ingredients}, ensure_ascii=False)
    return suggest_user_message(ingredients, names)


def payload_for(variant: str, ingredients: list[str], names: list[str]) -> dict:
    schema = MINIMAL_SCHEMA if variant == "V4" else SUGGEST_SCHEMA
    max_tokens = {"V0": 2048, "V1a": 1024, "V1b": 4096}.get(variant, CEILING)
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SUGGEST_SYSTEM},
            {"role": "user", "content": user_message(variant, ingredients, names)},
        ],
        "response_format": json_schema_format("dish_choice", schema),
        "provider": {"require_parameters": True},
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    if variant == "V3":
        payload["reasoning"] = {"enabled": False}
    return payload


def qualifies(metrics: dict, base: dict, truncated: int, skip: tuple[str, ...] = ()) -> bool:
    if truncated:
        return False
    for key in (
        "have_subset_share",
        "missing_disjoint_share",
        "reference_recall",
        "reference_precision",
        "reference_le2_missing_share",
    ):
        if key in skip or base.get(key) is None or metrics.get(key) is None:
            continue
        if metrics[key] < base[key] - 0.02:
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live-api", action="store_true")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "dish-tokens")
    args = parser.parse_args(argv)
    criteria = json.loads((HERE / "criteria.json").read_text(encoding="utf-8"))
    naive = json.loads((HERE.parent / "dish_naive" / "criteria.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c["ingredients"] for c in naive["cases"]}
    inputs = {i: by_id[i] for i in criteria["inputs"]["input_ids"]}
    variants = list(criteria["variants"])
    total = len(inputs) * len(variants)
    cap = criteria["max_model_calls"]
    print(f"{len(inputs)} inputs x {len(variants)} variants = {total} calls (cap {cap})")
    if not args.allow_live_api:
        print("dry run: no model call (use --allow-live-api)")
        return 0
    key = read_key()
    if not key:
        print("no OPENROUTER_API_KEY", file=sys.stderr)
        return 2
    catalog = Catalog.load()
    service = DishService(catalog)
    names = [d.name for d in service.catalog.all()]
    name_set = set(names)
    per_variant: dict[str, dict] = {}
    for variant in variants:
        rows, results = [], []
        for case_id, ingredients in inputs.items():
            call: Call = chat(payload_for(variant, ingredients, names), key)
            dishes = []
            raw_names: list[str] = []
            if call.data is not None:
                items = call.data.get("dishes")
                raw_names = (
                    [
                        d["name"]
                        for d in items
                        if isinstance(d, dict) and isinstance(d.get("name"), str)
                    ]
                    if isinstance(items, list)
                    else []
                )
                dishes = [
                    d.model_dump()
                    for d in check_suggest(call.data, service.catalog, service.recipes)
                ]
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
                    "id": case_id,
                    "ok": call.ok,
                    "error": call.error,
                    "dishes": len(dishes),
                    "call": call.__dict__ | {"data": None},
                }
            )
        calls = [r["call"] for r in rows]
        metrics = scoring.aggregate(results)
        per_variant[variant] = {
            "metrics": metrics,
            "calls": len(calls),
            "failed": sum(1 for r in rows if not r["ok"]),
            "truncated": sum(1 for c in calls if c["finish_reason"] == "length"),
            "mean_input": statistics.fmean(c["prompt_tokens"] for c in calls),
            "mean_output": statistics.fmean(c["completion_tokens"] for c in calls),
            "mean_reasoning": statistics.fmean(c["reasoning_tokens"] for c in calls),
            "mean_cached": statistics.fmean(c["cached_tokens"] for c in calls),
            "mean_cost_usd": statistics.fmean(c["cost_usd"] for c in calls),
            "median_latency_s": statistics.median(c["latency_s"] for c in calls),
            "rows": rows,
        }
        print(
            variant,
            {
                k: (round(v, 4) if isinstance(v, float) else v)
                for k, v in per_variant[variant].items()
                if k not in ("rows", "metrics")
            },
        )
    base = per_variant["B"]["metrics"]
    verdicts = {}
    for variant, v in per_variant.items():
        skip = ("have_subset_share",) if variant == "V4" else ()
        verdicts[variant] = qualifies(
            v["metrics"], base, v["truncated"] + (v["failed"] if variant != "V0" else 0), skip
        )
    winners = sorted(
        (v for v in per_variant if verdicts[v]),
        key=lambda v: (per_variant[v]["mean_cost_usd"], per_variant[v]["mean_output"]),
    )
    no_trunc = next(
        (v for v in ("V1a", "V0", "V1b", "B") if per_variant[v]["truncated"] == 0), None
    )
    summary = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        "qualifies": verdicts,
        "winner": winners[0] if winners else None,
        "smallest_no_truncation": no_trunc,
        "variants": per_variant,
        "total_calls": sum(v["calls"] for v in per_variant.values()),
        "total_cost_usd": sum(v["mean_cost_usd"] * v["calls"] for v in per_variant.values()),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"summary-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        "qualifies",
        verdicts,
        "winner",
        summary["winner"],
        "no-truncation",
        no_trunc,
        "cost",
        round(summary["total_cost_usd"], 4),
    )
    print("wrote", path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
