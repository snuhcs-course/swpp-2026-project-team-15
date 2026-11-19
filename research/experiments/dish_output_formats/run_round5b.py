# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Round 5 amendment: the limit said in the system text only (the answer format's maxItems is
rejected on this route). Reads round5.json for the served runs and the limits, adds B_say_mid and
B_say_high, and writes ``data/dish-formats/round5b.json``. Dry run by default."""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from experiments.dish_tokens.calls import read_key

from app.dishes.catalog import Catalog
from app.dishes.choices import ingredient_vocabulary

from . import formats, round5
from .run_formats import Budget, CapReached
from .run_round5 import cut, one_call, overlap, paired, summarize

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA = REPO_ROOT / "data/dish-formats"
RUNAWAY = [
    ("P1a", ["계란", "밥"]),
    ("P3a", ["밥", "계란", "외계인고기"]),
    ("P3b", ["밥", "달걀", "외계인고기"]),
]


def plan(cases: list[dict], limits: dict) -> list[tuple[str, str, list[str], int]]:
    calls = []
    for rep in range(2):
        for variant, k in (("B_say_mid", limits["K_mid"]), ("B_say_high", limits["K_high"])):
            calls += [(f"{variant}#{rep}", c["id"], c["ingredients"], k) for c in cases]
        calls += [(f"R_say_mid#{rep}", cid, ing, limits["K_mid"]) for cid, ing in RUNAWAY]
    return calls


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--allow-live-api", action="store_true")
    args = p.parse_args(argv)
    base = json.loads((DATA / "round5.json").read_text(encoding="utf-8"))
    limits = base["limits"]
    catalog = Catalog.load()
    vocab = ingredient_vocabulary(catalog.all())
    cases = round5.demo_cases() + [dict(c) for c in formats.frozen_cases()]
    calls = plan(cases, limits)
    print(f"{len(calls)} planned calls")
    if not args.allow_live_api:
        return 0
    key = read_key()
    budget = Budget(round5.criteria()["budget"]["model_calls"] - base["calls_attempted"])
    rows: dict[str, list[dict]] = {}
    try:
        for n, (group, cid, ingredients, k) in enumerate(calls):
            if n:
                time.sleep(1.0)
            row = one_call(cid, ingredients, k, (catalog, vocab), key, budget, in_schema=False)
            rows.setdefault(group.split("#")[0], []).append(row | {"run": group})
            print(n, group, cid, len(row["returned"]), row["latency_s"], file=sys.stderr)
    except CapReached:
        print("call cap reached", file=sys.stderr)
    served = base["runs"]["B_served"]
    after = {
        "B_after_mid": [cut(r, limits["K_mid"]) for r in served],
        "B_after_high": [cut(r, limits["K_high"]) for r in served],
    }
    metrics = ("dishes", "rules_missing_mean", "top5", "latency", "output_tokens")
    result = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "limits": limits,
        "calls_attempted": budget.used,
        "summary": {v: summarize(r) for v, r in rows.items()},
        "paired_vs_served": {v: paired(served, r, metrics) for v, r in rows.items()},
        "say_vs_cut": {
            "mid": overlap(rows.get("B_say_mid", []), after["B_after_mid"]),
            "high": overlap(rows.get("B_say_high", []), after["B_after_high"]),
        },
        "runs": rows,
    }
    (DATA / "round5b.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
