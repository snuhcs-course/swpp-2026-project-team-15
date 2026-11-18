# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Round 2 of the token study: does asking for less output lower the cost per call?

Baseline O0 and variant O1 are reused from the round-2 prompt study (``criteria_round2.json``);
O2 and O3 are fresh calls on the same 12 inputs. Dry run by default; ``--allow-live-api`` makes
the calls. Results go to the ignored ``data/dish-tokens/``.
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

from experiments.dish_naive import run_round2 as r2
from experiments.dish_naive import scoring
from experiments.dish_naive.run_naive import missing_counts, reference

from app.dishes.answers import check_suggest
from app.dishes.catalog import Catalog
from app.dishes.prompts import suggest_user_message
from app.dishes.service import DishService

from .calls import json_schema_format, read_key

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
STOP_SENTENCE = (
    " Order the dishes best first and stop listing as soon as the next dish would be a poor fit; "
    "fewer good dishes are better than a long list."
)
STRING_SENTENCE = (
    " Write 'missing' as one string of ingredient names separated by commas (an empty string if"
    " none)."
)
METRICS = (
    "have_subset_share",
    "missing_disjoint_share",
    "reference_recall",
    "reference_precision",
    "reference_le2_missing_share",
)


def split_missing(data: dict) -> dict:
    """O3: turn each comma-joined `missing` string back into a list (no matching rules)."""
    out = copy.deepcopy(data)
    for item in out.get("dishes", []) if isinstance(out.get("dishes"), list) else []:
        if isinstance(item, dict) and isinstance(item.get("missing"), str):
            item["missing"] = [p.strip() for p in item["missing"].split(",") if p.strip()]
    return out


def schema_for(base_variant: str, kind: str, ingredients: list[str]) -> dict:
    schema = r2.schema_for(base_variant, ingredients)
    item = schema["properties"]["dishes"]["items"]
    if kind == "O3":
        item["properties"]["missing"] = {"type": "string"}
    if kind == "O1":
        item["properties"].pop("have", None)
        item["required"] = ["name", "missing"]
    return schema


def payload_for(base: str, kind: str, ingredients: list[str], names: list[str]) -> dict:
    prompt = r2.prompts()[base]
    prompt += {"O2": STOP_SENTENCE, "O3": STRING_SENTENCE}.get(kind, "")
    return {
        "model": r2.MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": suggest_user_message(ingredients, names)},
        ],
        "response_format": json_schema_format("dish_choice", schema_for(base, kind, ingredients)),
        "provider": {"require_parameters": True},
        "max_tokens": r2.MAX_TOKENS,
        "temperature": 0,
    }


def score_rows(rows, inputs, catalog, service, name_set, drop_have=False) -> dict:
    results = []
    for row in rows:
        ingredients = inputs[row["id"]]
        data = row["call"].get("data")
        raw_names, dishes = [], []
        if data is not None:
            data = split_missing(data)
            items = data.get("dishes")
            if isinstance(items, list):
                raw_names = [
                    d["name"]
                    for d in items
                    if isinstance(d, dict) and isinstance(d.get("name"), str)
                ]
            dishes = [d.model_dump() for d in check_suggest(data, service.catalog, service.recipes)]
            if drop_have:
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
    calls = [r["call"] for r in rows]
    metrics = scoring.aggregate(results)
    if drop_have:
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


def qualifies(variant: dict, base: dict) -> bool:
    if variant["failed"] or variant["truncated"]:
        return False
    for key in METRICS:
        a, b = variant["metrics"].get(key), base["metrics"].get(key)
        if a is None or b is None:
            continue
        if a < b - 0.02:
            return False
    return True


def decide(per_variant: dict[str, dict]) -> dict:
    base = per_variant["O0"]
    qual = {k: qualifies(v, base) for k, v in per_variant.items() if k != "O0"}
    adoptable = [
        k
        for k in ("O2", "O3")
        if qual.get(k) and per_variant[k]["mean_cost_usd"] < base["mean_cost_usd"]
    ]
    adoptable.sort(key=lambda k: per_variant[k]["mean_cost_usd"])
    return {"qualifies": qual, "adopted": adoptable[0] if adoptable else None}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live-api", action="store_true")
    parser.add_argument("--round2", type=Path, help="round2-*.json of the prompt study")
    parser.add_argument("--base", help="variant of the prompt study to build on (default: adopted)")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "dish-tokens")
    args = parser.parse_args(argv)
    criteria = json.loads((HERE / "criteria_round2.json").read_text(encoding="utf-8"))
    tokens = json.loads((HERE / "criteria.json").read_text(encoding="utf-8"))
    naive = json.loads((HERE.parent / "dish_naive" / "criteria.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c["ingredients"] for c in naive["cases"]}
    inputs = {i: by_id[i] for i in tokens["inputs"]["input_ids"]}
    path = args.round2 or sorted((REPO_ROOT / "data" / "dish-naive").glob("round2-*.json"))[-1]
    study1 = json.loads(path.read_text(encoding="utf-8"))
    base = args.base or (study1["decision"] or {}).get("adopted") or "P0"
    fresh = ["O2", "O3"] + (["O1"] if base == "P0" else [])
    print(
        f"base prompt {base}; fresh calls: {len(fresh) * len(inputs)} (cap {criteria['call_cap']})"
    )
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
    reuse = lambda variant: [  # noqa: E731
        row for row in study1["variants"][variant]["rows"] if row["id"] in inputs
    ]
    per_variant = {"O0": score_rows(reuse(base), inputs, catalog, service, name_set)}
    if base != "P0":
        per_variant["O1"] = score_rows(reuse("P3"), inputs, catalog, service, name_set, True)
    r2.CALLS_MADE["n"] = 0
    for kind in fresh:
        rows = []
        for case_id, ingredients in inputs.items():
            call, attempts = r2.chat_with_retry(
                payload_for(base, kind, ingredients, names), key, criteria["call_cap"]
            )
            rows.append(
                {
                    "id": case_id,
                    "ok": call.ok,
                    "error": call.error,
                    "attempts": attempts,
                    "call": call.__dict__,
                }
            )
        per_variant[kind] = score_rows(rows, inputs, catalog, service, name_set, kind == "O1")
        v = per_variant[kind]
        print(
            kind,
            {k: (round(x, 4) if isinstance(x, float) else x) for k, x in v.items() if k != "rows"},
        )
    summary = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        "base_prompt": base,
        "round2_file": path.name,
        "decision": decide(per_variant),
        "variants": per_variant,
        "fresh_attempts": r2.CALLS_MADE["n"],
    }
    args.out.mkdir(parents=True, exist_ok=True)
    out = args.out / f"output-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("decision", json.dumps(summary["decision"]), "wrote", out.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
