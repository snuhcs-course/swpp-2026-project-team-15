# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Item 3: recipe rows that contain a staple's or an onboarding seasoning's name but are not
read as it (no model calls).

Run from server/:
    PYTHONPATH=. uv run python ../research/experiments/recheck_leftovers/scan_names.py \
    --recipes RECIPES.json --out FILE
"""

import argparse
import json
from pathlib import Path

from app.dishes.catalog import load_staples
from app.dishes.recipe_names import RecipeNames

ONBOARDING = ["소금", "설탕", "간장", "식용유", "참기름", "후추", "다진마늘", "고춧가루", "깨소금"]
ONBOARDING += ["식초", "고추장", "된장"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--recipes", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    names = RecipeNames.load()
    staples = sorted(load_staples() - {"물"})
    recipes = json.loads(Path(args.recipes).read_text(encoding="utf-8"))["recipes"]
    rows: dict[str, dict] = {}
    for dish_id, recipe in recipes.items():
        for row in recipe["ingredients"]:
            name = row["name"]
            for base in sorted(set(staples) | set(ONBOARDING), key=len, reverse=True):
                if base in name.replace(" ", "") and names.canonical(name) != base:
                    status = names.status(name, names.owned([base]))
                    if status != "owned" and status != "assumed":
                        entry = rows.setdefault(name, {"base": base, "dishes": []})
                        entry["dishes"].append(dish_id)
                    break
    result = {"unmapped": rows, "count": len(rows)}
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
    for name, e in sorted(rows.items()):
        print(name, "->", e["base"], len(e["dishes"]))


if __name__ == "__main__":
    main()
