# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Round 5 amendment 2: the served request with the output limit sized for K_high dishes, then the
server's order and cut. Reads round5.json, writes ``data/dish-formats/round5c.json``. Dry run by
default."""

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
from .run_round5 import cut, one_call, paired, summarize
from .run_round5b import RUNAWAY

DATA = Path(__file__).resolve().parents[3] / "data/dish-formats"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--allow-live-api", action="store_true")
    args = p.parse_args(argv)
    base = json.loads((DATA / "round5.json").read_text(encoding="utf-8"))
    k = base["limits"]["K_high"]
    served = base["runs"]["B_served"]
    room = round5.token_room(k, served)
    catalog = Catalog.load()
    vocab = ingredient_vocabulary(catalog.all())
    cases = round5.demo_cases() + [dict(c) for c in formats.frozen_cases()]
    calls = [
        (f"{g}#{rep}", cid, ing)
        for rep in range(2)
        for g, items in (
            ("B_tok", [(c["id"], c["ingredients"]) for c in cases]),
            ("R_tok", RUNAWAY),
        )
        for cid, ing in items
    ]
    print(f"{len(calls)} planned calls, output limit {room} tokens for K_high = {k}")
    if not args.allow_live_api:
        return 0
    key = read_key()
    budget = Budget(len(calls) + 6)
    rows: dict[str, list[dict]] = {}
    try:
        for n, (group, cid, ingredients) in enumerate(calls):
            if n:
                time.sleep(1.0)
            row = one_call(cid, ingredients, None, (catalog, vocab), key, budget, max_tokens=room)
            row = cut(row, k) | {"run": group, "latency_s": row["latency_s"]}
            rows.setdefault(group.split("#")[0], []).append(row)
            print(n, group, cid, row["raw_count"], row["latency_s"], file=sys.stderr)
    except CapReached:
        print("call cap reached", file=sys.stderr)
    after = [cut(r, k) for r in served]
    metrics = ("dishes", "rules_missing_mean", "top5", "latency", "output_tokens")
    result = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "k": k,
        "output_limit": room,
        "calls_attempted": budget.used,
        "summary": {v: summarize(r) for v, r in rows.items()} | {"B_after_high": summarize(after)},
        "paired_vs_after_high": {v: paired(after, r, metrics) for v, r in rows.items()},
        "runs": rows,
    }
    (DATA / "round5c.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), "utf-8")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
