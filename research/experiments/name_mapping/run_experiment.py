# AI-generated with Claude Code (Sonnet 5.5), 2026-11-04; reviewed by Jaehyuk Choi.
"""Score name resolution against a hand-labelled gold file; offline, no model API calls.

    PYTHONPATH=server:research uv run --project server --locked \
        python -m experiments.name_mapping.run_experiment --db PATH --names names.json \
        --gold gold.json

Inputs (private, not in the repository):
  --db     SQLite recipe database (read-only; table ``ingredient``).
  --names  JSON list of [name, count]: model-produced names with how often each occurred.
  --gold   JSON object: name -> table name it should map to, or null when the table has no
           counterpart. Written by hand; label before looking at any resolver output.
By default only exact and synonym matching run. ``--embedder fastembed`` adds the embedding step
(needs ``uv run --with fastembed``; downloads the model once); ``--tau`` takes a list to sweep.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Mapping, Sequence

from experiments.name_mapping.resolver import Resolver, fastembed_embedder


def load_catalog(db_path: str) -> dict[int, str]:
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return dict(con.execute("SELECT ingredient_id, name FROM ingredient"))
    finally:
        con.close()


def evaluate(
    resolver: Resolver,
    counts: Sequence[tuple[str, int]],
    gold: Mapping[str, str | None],
) -> dict[str, float]:
    """Occurrence-weighted shares: mapped right, mapped wrong, left unmapped (right or wrong)."""
    tally = {
        "mapped_correct": 0,
        "mapped_wrong": 0,
        "unmapped_correct": 0,
        "unmapped_wrong": 0,
    }
    total = 0
    for name, n in counts:
        if name not in gold:
            continue
        want, got = gold[name], resolver.resolve(name).name
        total += n
        if got is None:
            key = "unmapped_correct" if want is None else "unmapped_wrong"
        else:
            key = "mapped_correct" if got == want else "mapped_wrong"
        tally[key] += n
    return {k: v / total if total else 0.0 for k, v in tally.items()}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", required=True)
    ap.add_argument("--names", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--embedder", choices=["none", "fastembed"], default="none")
    ap.add_argument("--tau", type=float, nargs="+", default=[0.99])
    ap.add_argument("--margin", type=float, default=0.10)
    args = ap.parse_args(argv)
    catalog = load_catalog(args.db)
    with open(args.names, encoding="utf-8") as f:
        counts = [(n, c) for n, c in json.load(f)]
    with open(args.gold, encoding="utf-8") as f:
        gold = json.load(f)
    embed = fastembed_embedder() if args.embedder == "fastembed" else None
    for tau in args.tau if embed else [None]:
        resolver = Resolver(catalog, embed, tau if tau is not None else 1.01, args.margin)
        shares = evaluate(resolver, counts, gold)
        label = "exact+synonym" if tau is None else f"tau={tau} margin={args.margin}"
        print(label, json.dumps({k: round(v, 4) for k, v in shares.items()}))


if __name__ == "__main__":
    main()
