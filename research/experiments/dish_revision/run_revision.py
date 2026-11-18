# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
"""Run the frozen revision cases through the real server code.

Default: a dry run that prints the plan and makes no model call. ``--allow-live-api`` makes one
model call per case (key from OPENROUTER_API_KEY or ~/.config/mylittlechef/); the server retries a
429 itself and every request is counted. Results go to the ignored ``data/dish-revision/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

from experiments.dish_naive.run_naive import RecordingLLM, Usage, UsageTransport, git
from experiments.dish_tokens.calls import read_key

from app.dishes.catalog import Catalog
from app.dishes.llm import DEFAULT_MODEL, DishLLM, DishLLMError
from app.dishes.recipes import RecipeStore
from app.dishes.revision import Reviser

from . import scoring

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
PRICE_PER_MTOK = (0.10, 0.40)
CALL_CAP = 80


def load() -> tuple[RecipeStore, list[dict]]:
    store = RecipeStore.load(HERE / "fixtures.json")
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))["cases"]
    return store, cases


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def request_cost(row: dict) -> float:
    if row.get("cost") is not None:
        return float(row["cost"])
    p, c = row.get("prompt_tokens", 0), row.get("completion_tokens", 0)
    return (p * PRICE_PER_MTOK[0] + c * PRICE_PER_MTOK[1]) / 1e6


def run_case(case: dict, store: RecipeStore, catalog: Catalog, llm: RecordingLLM, usage: Usage):
    before = len(usage.rows)
    reviser = Reviser(catalog, llm, store)
    row = {"id": case["id"], "expect": case["expect"], "status": "error", "valid": False}
    try:
        result = reviser.revise(case["dish_id"], case["ingredients"])
        row["valid"] = True
        row["status"] = result.status
        if result.error:
            row["error_code"] = result.error.code
        row["refusal_reason"] = result.refusal_reason
    except DishLLMError as exc:
        row["error"] = str(exc)
    requests = usage.rows[before:]
    row["requests"] = len(requests)
    ok = [r for r in requests if r["status"] == 200]
    row["latency_s"] = ok[-1]["latency_s"] if ok else None
    row["cost_usd"] = sum(request_cost(r) for r in requests)
    row["prompt_tokens"] = sum(r.get("prompt_tokens", 0) for r in requests)
    row["completion_tokens"] = sum(r.get("completion_tokens", 0) for r in requests)
    raw = llm.last
    recipe = store.get(case["dish_id"])
    if raw and raw.get("can_revise") is True:
        row["ingredient_coverage"] = scoring.ingredient_coverage(recipe, raw)
        row["step_coverage"] = scoring.step_coverage(recipe, raw)
    return row, raw


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live-api", action="store_true")
    parser.add_argument("--only", help="comma-separated case ids (for a repeat after an outage)")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "dish-revision")
    args = parser.parse_args(argv)
    store, cases = load()
    if args.only:
        wanted = set(args.only.split(","))
        cases = [c for c in cases if c["id"] in wanted]
    print(f"{len(cases)} cases, model {DEFAULT_MODEL}, call cap {CALL_CAP}")
    if not args.allow_live_api:
        print("dry run: no model call (use --allow-live-api)")
        return 0
    key = read_key()
    if not key:
        print("no OpenRouter key found", file=sys.stderr)
        return 2
    usage = Usage()
    llm = RecordingLLM(DishLLM(key, DEFAULT_MODEL, transport=UsageTransport(usage)))
    catalog = Catalog.load()
    rows, raws = [], {}
    for case in cases:
        if len(usage.rows) >= CALL_CAP:
            print("call cap reached; stopping", file=sys.stderr)
            break
        row, raw = run_case(case, store, catalog, llm, usage)
        rows.append(row)
        raws[case["id"]] = raw
        print(
            f"{case['id']} expect={case['expect']} -> {row['status']} {row.get('error_code', '')}"
        )
    metrics = scoring.summarize(rows)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    args.out.mkdir(parents=True, exist_ok=True)
    summary = {
        "date": stamp,
        "commit": git("rev-parse", "HEAD"),
        "model": DEFAULT_MODEL,
        "python": platform.python_version(),
        "criteria_sha256": sha256(HERE / "criteria.json"),
        "cases_sha256": sha256(HERE / "cases.json"),
        "fixtures_sha256": sha256(HERE / "fixtures.json"),
        "requests": len(usage.rows),
        "metrics": metrics,
        "verdicts": scoring.verdicts(metrics),
        "rows": rows,
    }
    (args.out / f"summary-{stamp}.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    (args.out / f"raw-{stamp}.json").write_text(
        json.dumps(raws, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(json.dumps({"metrics": metrics, "verdicts": summary["verdicts"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
