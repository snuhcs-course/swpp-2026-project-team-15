# AI-generated with Claude Code (Opus 5.5), 2026-11-19; not yet reviewed.
"""Suggestions for fridges that share no key ingredient with any dish, and for ordinary fridges.

Runs the served suggestion path (DishService with the real model) of a server tree and records,
per run, the dishes and how many have a `have` list that covers none of the dish's ingredients.

    uv run python ../research/experiments/e2e_followups/suggest_unrelated.py \
        --server-dir . --runs 3 --out FILE --allow-network
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

CONFIG = Path.home() / ".config" / "mylittlechef" / "openrouter.env"

UNRELATED = [["초콜릿"], ["우유"], ["사과"], ["콜라"], ["과자"], ["바나나"]]
ORDINARY = [
    ["계란", "밥"],
    ["김치", "밥"],
    ["두부"],
    ["양파", "대파", "감자"],
    ["햇반", "계란"],
    ["참치캔", "김"],
]


def read_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key and CONFIG.exists():
        for line in CONFIG.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("\"'")
    return key


def unsupported(catalog, dish_id: str, have: list[str]) -> bool:
    """True when no `have` entry covers a key or optional ingredient of the dish."""
    dish = catalog.get(dish_id)
    wanted = set(dish.key_ingredients) | set(dish.optional)
    owned = catalog.owned(have)
    return not any(key in owned or catalog._covered(key, owned) for key in wanted)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server-dir", required=True)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", choices=["unrelated", "ordinary", "all"], default="all")
    ap.add_argument("--model", default="")
    ap.add_argument("--allow-network", action="store_true")
    args = ap.parse_args()
    if not args.allow_network:
        sys.exit("refusing to call the model without --allow-network")
    sys.path.insert(0, str(Path(args.server_dir).resolve()))
    from app.dishes.llm import DEFAULT_MODEL, DishLLM  # noqa: E402
    from app.dishes.service import DishService  # noqa: E402

    llm_model = args.model or DEFAULT_MODEL  # the served model by default
    # Build the service the way the running app does (staples as assumed names), when the tree has
    # the app's builder; older trees fall back to their own builder.
    env = {"DISH_LLM_API_KEY": read_key(), "DISH_LLM_MODEL": llm_model}
    try:
        from app.config import Settings  # noqa: E402
        from app.dishes.dependencies import build_dish_parts  # noqa: E402

        service = build_dish_parts(Settings.from_env(env)).service
    except ImportError:
        from app.dishes.dependencies import build_dish_service  # noqa: E402

        service = build_dish_service(env)
    catalog = service.catalog
    _ = (DishLLM, DishService)
    inputs = {"unrelated": UNRELATED, "ordinary": ORDINARY}
    groups = ["unrelated", "ordinary"] if args.only == "all" else [args.only]
    rows = []
    for group in groups:
        for fridge in inputs[group]:
            for run in range(args.runs):
                started = time.monotonic()
                try:
                    answer = service.suggest(fridge)
                    dishes = [
                        {"id": d.id, "have": d.have, "missing": d.missing} for d in answer.dishes
                    ]
                    error = None
                except Exception as exc:  # noqa: BLE001 - record and go on
                    dishes, error = [], type(exc).__name__
                rows.append(
                    {
                        "group": group,
                        "fridge": fridge,
                        "run": run,
                        "seconds": round(time.monotonic() - started, 2),
                        "dishes": len(dishes),
                        "unsupported": sum(
                            unsupported(catalog, d["id"], d["have"]) for d in dishes
                        ),
                        "answer": dishes,
                        "error": error,
                    }
                )
                print(
                    group,
                    fridge,
                    run,
                    rows[-1]["dishes"],
                    rows[-1]["unsupported"],
                    rows[-1]["seconds"],
                )
    out = {
        "at": datetime.now(UTC).isoformat(timespec="seconds"),
        "server_dir": args.server_dir,
        "model": llm_model,
        "rows": rows,
    }
    Path(args.out).write_text(
        json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
