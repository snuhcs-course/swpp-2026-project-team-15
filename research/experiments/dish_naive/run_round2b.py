# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Round 2b of the naive dish study: P0 and P1 of round 2 on the same 27 inputs with the output
cap raised to 8192 tokens. The rule is frozen in ``criteria_round2b.json``. Dry run by default;
``--allow-live-api`` makes the planned calls. Results go to the ignored ``data/dish-naive/``.
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from experiments.dish_tokens.calls import read_key

from app.dishes.catalog import Catalog
from app.dishes.service import DishService

from . import run_round2

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[2]
MAX_TOKENS = 8192
VARIANTS = ("P0", "P1")


def decide(per_variant: dict[str, dict]) -> dict:
    """Apply the frozen rule: is P1 adopted, and which condition fails if not."""
    base, p1 = per_variant["P0"], per_variant["P1"]
    bm, m = base["metrics"], p1["metrics"]
    checks = {
        "no_truncation_or_failure": p1["truncated"] == 0 and p1["failed"] == 0,
        "have_subset>=0.99": (m.get("have_subset_share") or 0) >= 0.99,
        "valid_names>=P0": m["valid_names_share"] >= bm["valid_names_share"],
        "nonempty>=P0-0.02": m["nonempty_when_possible"] >= bm["nonempty_when_possible"] - 0.02,
        "recall>=P0-0.02": m["reference_recall"] >= bm["reference_recall"] - 0.02,
        "precision>=P0-0.02": m["reference_precision"] >= bm["reference_precision"] - 0.02,
        "cost<=1.15xP0": p1["mean_cost_usd"] <= 1.15 * base["mean_cost_usd"],
    }
    adopted = all(checks.values())
    return {
        "checks": checks,
        "failed_checks": [k for k, ok in checks.items() if not ok],
        "adopted": "P1" if adopted else None,
        "p0_cap_only": (not adopted) and base["truncated"] == 0 and base["failed"] == 0,
    }


def dish_counts(variant_result: dict) -> dict:
    counts = [len(r["returned"]) for r in variant_result["rows"] if r["ok"]]
    return {
        "per_input": {r["id"]: len(r["returned"]) for r in variant_result["rows"]},
        "min": min(counts, default=None),
        "median": statistics.median(counts) if counts else None,
        "max": max(counts, default=None),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allow-live-api", action="store_true")
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "data" / "dish-naive")
    args = parser.parse_args(argv)
    criteria = json.loads((HERE / "criteria_round2b.json").read_text(encoding="utf-8"))
    naive = json.loads((HERE / "criteria.json").read_text(encoding="utf-8"))
    cases = [c for c in naive["cases"] if c["expect_status"] == 200]
    cap = criteria["call_cap"]
    total = len(cases) * len(VARIANTS)
    print(f"{len(cases)} inputs x {len(VARIANTS)} variants = {total} calls (cap {cap})")
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
    for variant in VARIANTS:
        per_variant[variant] = run_round2.run_variant(
            variant, cases, names, set(names), catalog, service, key, cap, MAX_TOKENS
        )
        v = per_variant[variant]
        v["dish_counts"] = dish_counts(v)
        v["max_latency_s"] = max(r["call"]["latency_s"] for r in v["rows"])
        v["attempts"] = sum(r["attempts"] for r in v["rows"])
        print(
            variant,
            {
                k: (round(x, 4) if isinstance(x, float) else x)
                for k, x in v.items()
                if k not in ("rows", "dish_counts")
            },
        )
    summary = {
        "date": datetime.now(UTC).isoformat(timespec="seconds"),
        "commit": subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "HEAD"], capture_output=True, text=True
        ).stdout.strip(),
        "max_tokens": MAX_TOKENS,
        "decision": decide(per_variant),
        "variants": per_variant,
        "attempts": run_round2.CALLS_MADE["n"],
        "total_cost_usd": sum(v["mean_cost_usd"] * v["calls"] for v in per_variant.values()),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / f"round2b-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("decision", json.dumps(summary["decision"], ensure_ascii=False))
    print("cost", round(summary["total_cost_usd"], 4), "wrote", path.relative_to(REPO_ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
