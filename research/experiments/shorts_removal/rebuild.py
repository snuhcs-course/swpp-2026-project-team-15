# AI-generated with Claude Code (Opus 5.5), 2026-11-19; not yet reviewed.
"""Rebuild recipes for vertical-source dishes and main-ingredient-mismatch dishes.

Run from pr-work/ytdemo/server with PYTHONPATH=.:../research after the first build finished.
For each dish: try the stored landscape videos in order (skipping the served recipe's own video
for mismatch dishes); accept the first valid recipe whose main rows are all available with the
fridge = the dish's key ingredients (round-3 offline measure, reviewed name table).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from app.dishes.catalog import Catalog
from app.dishes.recipe_names import RecipeNames
from experiments.dish_recipes import video_recipes as vr
from experiments.dish_recipes.common import now_iso
from experiments.dish_recipes.validate_recipe import check_recipe

ROOT = Path("/home/hyuk/PRJ/MyLittleChef/artifacts/dish-recipes")
W = ROOT / "shorts-removal"
MODEL = "google/gemini-2.5-flash"
MAX_COST = float(os.environ.get("YRD_MAX_COST", "8"))


def write(path: Path, value) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1), encoding="utf-8")
    os.chmod(tmp, 0o600)
    tmp.replace(path)


def main() -> int:
    live = "--live" in sys.argv
    cat, names = Catalog.load(), RecipeNames.load()
    vertical = set(json.loads((ROOT / "orientation.json").read_text())["summary"]["recipes_from_vertical"])
    r3 = json.loads(Path("../data/dish-revision/round3-20261119T015432Z.json").read_text())
    mismatch = set(r3["offline"]["N1"]["main_unavailable_ids"])
    served = json.loads((ROOT / "recipes.json").read_text())["recipes"]
    links = json.loads((ROOT / "link-data/dish-videos.verified.json").read_text())["dishes"]
    built = json.loads((W / "recipe-build/recipes.json").read_text())["recipes"]
    breport = json.loads((W / "recipe-build/build-report.json").read_text())["dishes"]
    state_path = W / "yrd-state.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"dishes": {}, "cost": 0.0, "calls": 0}

    def main_gap(dish: str, recipe: dict) -> list[str]:
        owned = names.owned(list(cat.get(dish).key_ingredients))
        return [r["name"] for r in recipe["ingredients"]
                if r["role"] == "main" and names.status(r["name"], owned) == "unavailable"]

    for dish in sorted(vertical | mismatch):
        st = state["dishes"].setdefault(dish, {"tries": {}, "vertical": dish in vertical,
                                               "mismatch_before": dish in mismatch})
        if st.get("final"):
            continue
        # tries of the first build are reused (same model, same checks)
        for t in breport.get(dish, {}).get("tries", []):
            st["tries"].setdefault(t["video"], {
                "valid": bool(built.get(dish, {}).get("video", {}).get("id") == t["video"]),
                "cooked_dish": t["cooked_dish"], "cost": t["cost_usd"], "from": "first_build"})
            if st["tries"][t["video"]]["valid"]:
                st["tries"][t["video"]]["recipe"] = built[dish]
        old_vid = served.get(dish, {}).get("video", {}).get("id")
        cands = [v["id"] for v in links.get(dish, {}).get("videos", []) if not (dish in mismatch and v["id"] == old_vid)]
        accepted = None
        for vid in cands:
            t = st["tries"].get(vid)
            if t is None:
                if not live or state["cost"] >= MAX_COST:
                    break
                res = vr.call(vr.build_payload(cat.get(dish).name, vid, MODEL))
                state["cost"] += res.cost_usd
                state["calls"] += 1
                ans = res.answer or {}
                rec = vr.to_recipe(dish, {"id": vid}, ans) if ans else None
                probs = check_recipe(rec, None) if rec else ["no recipe" if res.ok else res.error]
                t = st["tries"][vid] = {"valid": bool(rec and not probs), "problems": probs,
                                        "cooked_dish": ans.get("cooked_dish", ""), "cost": res.cost_usd,
                                        "from": "yrd", "is_requested_dish": ans.get("is_requested_dish")}
                if t["valid"]:
                    t["recipe"] = rec
                write(state_path, state)
            if t["valid"]:
                t["main_gap"] = main_gap(dish, t["recipe"])
                if not t["main_gap"]:
                    accepted = vid
                    break
        else:
            pass
        exhausted = all(v in st["tries"] for v in cands)
        if accepted or exhausted:
            st["final"] = True
            st["accepted"] = accepted
            st["candidates"] = len(cands)
        write(state_path, state)
        print(dish, "accepted" if accepted else ("exhausted" if exhausted else "pending"),
              len(st["tries"]), f"${state['cost']:.2f}", flush=True)
    print("calls", state["calls"], "cost", round(state["cost"], 4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
