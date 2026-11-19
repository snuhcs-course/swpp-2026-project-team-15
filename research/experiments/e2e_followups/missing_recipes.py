# AI-generated with Claude Code (Opus 5.5), 2026-11-19; not yet reviewed.
"""Recipes for the dishes that have none, from their stored landscape videos in order.

Run from pr-work/ytdemo/server with PYTHONPATH=.:../research:

    uv run python ../research/experiments/e2e_followups/missing_recipes.py \
        --root ARTIFACTS_DIR --state FILE --live DISH...

A video is tried with the same video-input build and checks as before; the recipe is accepted only
when the model says the video cooks the requested dish and, with the fridge = the dish's key
ingredients and the server's name table, no main row is unavailable. Stops at the first accepted
video per dish. Video data and recipes stay outside git.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from experiments.dish_recipes import video_recipes as vr
from experiments.dish_recipes.validate_recipe import check_recipe

from app.dishes.catalog import Catalog
from app.dishes.recipe_names import RecipeNames

MODEL = "google/gemini-2.5-flash"


def arg(flag: str) -> Path:
    if flag not in sys.argv or sys.argv.index(flag) + 1 >= len(sys.argv):
        raise SystemExit(f"pass {flag} PATH")
    return Path(sys.argv[sys.argv.index(flag) + 1])


def save(path: Path, value) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def main_gap(cat: Catalog, names: RecipeNames, dish: str, recipe: dict) -> list[str]:
    owned = names.owned(list(cat.get(dish).key_ingredients))
    return [
        r["name"]
        for r in recipe["ingredients"]
        if r["role"] == "main" and names.status(r["name"], owned) == "unavailable"
    ]


def main() -> None:
    if "--live" not in sys.argv:
        raise SystemExit("refusing to call the model without --live")
    root, state_path = arg("--root"), arg("--state")
    dishes = [a for a in sys.argv[1:] if not a.startswith("--") and "/" not in a]
    names = RecipeNames.load()
    cat = Catalog.load(names=names)
    links = json.loads((root / "link-data" / "dish-videos.verified.json").read_text())["dishes"]
    state = json.loads(state_path.read_text()) if state_path.exists() else {"calls": 0, "cost": 0.0}
    for dish in dishes:
        entry = state.setdefault(dish, {"tries": {}})
        for video in links[dish]["videos"]:
            vid = video["id"]
            if vid in entry["tries"]:
                if entry["tries"][vid].get("accepted"):
                    break
                continue
            res = vr.call(vr.build_payload(cat.get(dish).name, vid, MODEL))
            state["calls"] += 1
            state["cost"] += res.cost_usd
            ans = res.answer or {}
            rec = vr.to_recipe(dish, {"id": vid}, ans) if ans else None
            problems = check_recipe(rec, None) if rec else ["no recipe" if res.ok else res.error]
            t = entry["tries"][vid] = {
                "valid": bool(rec and not problems),
                "problems": problems,
                "cooked_dish": ans.get("cooked_dish", ""),
                "is_requested_dish": ans.get("is_requested_dish"),
                "cost": res.cost_usd,
            }
            if t["valid"]:
                t["recipe"] = rec
                t["main_gap"] = main_gap(cat, names, dish, rec)
            t["accepted"] = bool(t["valid"] and t["is_requested_dish"] and not t.get("main_gap"))
            save(state_path, state)
            print(dish, vid, t["accepted"], t["cooked_dish"], t.get("main_gap"), problems[:1])
            if t["accepted"]:
                break
    print("calls", state["calls"], "cost", round(state["cost"], 3))


if __name__ == "__main__":
    main()
