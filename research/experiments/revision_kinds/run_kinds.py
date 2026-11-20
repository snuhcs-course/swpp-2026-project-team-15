# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Change kinds over every stored recipe, fridge = the dish's key ingredients (served path).

Run from server/:
    PYTHONPATH=. uv run python ../research/experiments/revision_kinds/run_kinds.py \
    --recipes RECIPES.json --out FILE [--workers 8]
Needs the dish model key in the environment. Saves outcomes and kinds, not recipe text.
"""

import argparse
import json
import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app.config import Settings
from app.dishes.catalog import Catalog
from app.dishes.dependencies import build_dish_parts
from app.dishes.errors import DishLLMError
from app.dishes.recipe_names import RecipeNames


def implied(change, source, revised_names: set[str], names: RecipeNames) -> str | None:
    """omission / substitution from the rows; None when the rows do not decide it."""
    rows = [source.ingredients[i - 1] for i in change.ingredient_refs]
    if not rows:
        return None
    gone = all(names.canonical(r.name) not in revised_names for r in rows)
    if not gone:
        return None
    source_names = {names.canonical(r.name) for r in source.ingredients}
    added = revised_names - source_names
    return "substitution" if added else "omission"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipes", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    env = {**os.environ, "DISH_RECIPES": args.recipes}
    parts = build_dish_parts(Settings.from_env(env))
    names = RecipeNames.load()
    catalog = Catalog.load(names=names)
    store = json.loads(Path(args.recipes).read_text(encoding="utf-8"))["recipes"]
    from app.dishes.recipes import RecipeStore

    sources = RecipeStore.load(args.recipes)

    def one(dish):
        try:
            result = parts.reviser.revise(dish.id, list(dish.key_ingredients))
        except DishLLMError:
            return {"dish": dish.id, "status": "failed", "code": "model_error"}
        row = {"dish": dish.id, "status": result.status}
        if result.status == "failed":
            row["code"] = result.error.code
        if result.status == "revised":
            source = sources.get(dish.id)
            revised_names = {names.canonical(i.name) for i in result.revised.ingredients}
            row["changes"] = [
                {"kind": c.kind, "implied": implied(c, source, revised_names, names)}
                for c in result.changes
            ]
        return row

    dishes = [d for d in catalog.all() if d.id in store]
    with ThreadPoolExecutor(args.workers) as pool:
        rows = list(pool.map(one, dishes))
    outcomes = Counter(
        r["status"] if r["status"] != "failed" else "failed:" + r["code"] for r in rows
    )
    pairs = Counter((c["kind"], c["implied"]) for r in rows for c in r.get("changes", []))
    decided = [(k, i) for (k, i), n in pairs.items() for _ in range(n) if i is not None]
    agree = sum(1 for k, i in decided if k == i)
    summary = {
        "recipes": len(rows),
        "outcomes": dict(outcomes),
        "kind_counts": dict(Counter(c["kind"] for r in rows for c in r.get("changes", []))),
        "pairs": {f"{k}|{i}": n for (k, i), n in pairs.items()},
        "decided_by_rows": len(decided),
        "agree": agree,
    }
    Path(args.out).write_text(
        json.dumps({"summary": summary, "rows": rows}, ensure_ascii=False, indent=1) + "\n"
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
