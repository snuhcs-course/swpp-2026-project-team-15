# AI-generated with Claude Code (Opus 5.5), 2026-11-19; not yet reviewed.
"""New videos for the eight dishes whose every stored video uses an extra main ingredient.

Run from pr-work/ytdemo/server with PYTHONPATH=.:../research. Data stay outside git.
Stages: collect --live | judge --live | show | build --live <dish> <video>... | merge,
each with --root DATA_DIR.
One official search per dish names the version without the extra main; candidates already
stored or judged for the dish are skipped; landscape, public, embeddable only; the two validated
judges answer relevance; a person reads the candidates; a recipe is built from a read candidate
and accepted only when no main row is unavailable with the fridge = the dish's key ingredients.
"""

from __future__ import annotations

import json
import os
import shutil
import sys

import httpx
from experiments.dish_recipes import video_recipes as vr
from experiments.dish_recipes.common import load_json, now_iso, read_key
from experiments.dish_recipes.search_videos import SEARCH_URL, result_ids, search_params
from experiments.dish_recipes.validate_recipe import check_recipe
from experiments.dish_recipes.verify_videos import (
    JUDGE_PROMPT,
    JUDGES,
    chat,
    dish_table,
    item_text,
    playable,
)
from experiments.shorts_removal.refill import details, parse, path_arg, private, seen_ids

from app.dishes.catalog import Catalog
from app.dishes.recipe_names import RecipeNames

ROOT = path_arg("--root")  # the artifacts/dish-recipes folder (outside git)
LINKS = ROOT / "link-data"
W = ROOT / "shorts-removal"
STATE = W / "yrd-search.json"
VERIFIED = LINKS / "dish-videos.verified.json"
RECIPES = ROOT / "recipes.json"
MODEL = "google/gemini-2.5-flash"
KEEP = 5

QUERIES = {
    "bulgogi-bowl": "소불고기덮밥 만들기",
    "curry-rice": "야채카레 만들기",
    "bibimbap": "야채비빔밥 만들기",
    "spam-kimchi-stew": "햄 김치찌개 만들기",
    "gochujang-stew": "감자 애호박 고추장찌개",
    "radish-soup": "멸치 무국 끓이는법",
    "rice-cake-soup": "멸치육수 떡국 끓이는법",
    "tuna-gimbap": "참치김밥 만들기",
}


def main_gap(cat: Catalog, names: RecipeNames, dish: str, recipe: dict) -> list[str]:
    owned = names.owned(list(cat.get(dish).key_ingredients))
    return [
        r["name"]
        for r in recipe["ingredients"]
        if r["role"] == "main" and names.status(r["name"], owned) == "unavailable"
    ]


def collect() -> None:
    yt = read_key("YOUTUBE_API_KEY", "youtube.env")
    state = load_json(STATE, {"dishes": {}, "units": 0, "or_calls": 0, "or_cost": 0.0})
    stored = load_json(VERIFIED, {})["dishes"]
    for dish, q in QUERIES.items():
        e = state["dishes"].setdefault(dish, {})
        if "candidates" in e:
            continue
        r = httpx.get(
            SEARCH_URL, params=search_params(q), headers={"X-Goog-Api-Key": yt}, timeout=30
        )
        state["units"] += 100
        if r.status_code != 200:
            private(STATE, state)
            raise SystemExit(f"{dish}: search HTTP {r.status_code}")
        ids = result_ids(r.json())
        seen = seen_ids(dish) | {v["id"] for v in stored.get(dish, {}).get("videos", [])}
        order = [v for v in dict.fromkeys(ids) if v not in seen]
        info = details(yt, order) if order else {}
        state["units"] += (len(order) + 49) // 50
        keep = [
            v
            for v in order
            if v in info
            and playable(info[v])
            and info[v]["orientation"] in ("horizontal", "square")
        ]
        e.update(
            q=q,
            at=now_iso(),
            results=ids,
            new=order,
            order=keep,
            dropped={
                v: (
                    "gone"
                    if v not in info
                    else "not_playable"
                    if not playable(info[v])
                    else info[v]["orientation"]
                )
                for v in order
                if v not in keep
            },
            candidates={v: info[v] for v in keep},
        )
        private(STATE, state)
        print(f"{dish}: results {len(ids)} new {len(order)} landscape-playable {len(keep)}")


def judge() -> None:
    key = read_key("OPENROUTER_API_KEY", "openrouter.env")
    state, table = load_json(STATE, {}), dish_table()
    for dish, e in state["dishes"].items():
        e.setdefault("judged", {})
        keys = [f"{dish}|{v}" for v in e["order"] if f"{dish}|{v}" not in e["judged"]]
        for n in range(0, len(keys), 6):
            part = keys[n : n + 6]
            items = "\n".join(
                item_text(k, table[dish], e["candidates"][k.split("|", 1)[1]]) for k in part
            )
            for model in JUDGES:
                res = chat(key, model, JUDGE_PROMPT.format(items=items))
                parsed = parse(res.get("text", ""), part) if "error" not in res else None
                state["or_cost"] += res["cost"]
                state["or_calls"] += res["calls"]
                for k in part:
                    e["judged"].setdefault(k, {})[model] = (parsed or {}).get(k)
        private(STATE, state)
        print(dish, "judged", len(keys))


def show() -> None:
    state, table = load_json(STATE, {}), dish_table()
    for dish, e in state["dishes"].items():
        print(f"== {dish} {table[dish]['name']} ({e['q']})")
        for v in e["order"]:
            c, j = e["candidates"][v], e.get("judged", {}).get(f"{dish}|{v}", {})
            js = "/".join(
                {True: "Y", False: "N", None: "?"}[(j.get(m) or {}).get("relevant")] for m in JUDGES
            )
            print(
                f"{v} {js} {c['duration_s']}s {c['orientation'][0]} | {c['channel']} | {c['title'][:70]} | {c['description'][:120]!r}"
            )


def build(dish: str, vids: list[str]) -> None:
    cat, names = Catalog.load(), RecipeNames.load()
    state = load_json(STATE, {})
    e = state["dishes"][dish]
    tries = e.setdefault("tries", {})
    for vid in vids:
        if vid in tries:
            continue
        res = vr.call(vr.build_payload(cat.get(dish).name, vid, MODEL))
        state["or_cost"] += res.cost_usd
        state["or_calls"] += 1
        ans = res.answer or {}
        rec = vr.to_recipe(dish, {"id": vid}, ans) if ans else None
        probs = check_recipe(rec, None) if rec else ["no recipe" if res.ok else res.error]
        t = tries[vid] = {
            "valid": bool(rec and not probs),
            "problems": probs,
            "cost": res.cost_usd,
            "cooked_dish": ans.get("cooked_dish", ""),
            "is_requested_dish": ans.get("is_requested_dish"),
        }
        if t["valid"]:
            t["recipe"] = rec
            t["main_gap"] = main_gap(cat, names, dish, rec)
        private(STATE, state)
        print(
            dish,
            vid,
            "valid" if t["valid"] else probs,
            t.get("main_gap"),
            t["cooked_dish"],
            f"${res.cost_usd:.3f}",
        )
        if t["valid"] and not t["main_gap"]:
            break


def merge() -> None:
    """Reviewed links (state 'review': {dish: [ids]}) go after the stored ones up to KEEP;
    the accepted recipe ('accept': {dish: id}) replaces the served one."""
    state = load_json(STATE, {})
    for path, backup in (
        (VERIFIED, LINKS / "dish-videos.verified.pre-yrd-search.json"),
        (RECIPES, ROOT / "recipes.pre-yrd-search.json"),
    ):
        if not backup.exists():
            shutil.copy2(path, backup)
            os.chmod(backup, 0o600)
    links = load_json(VERIFIED, {})
    recipes = load_json(RECIPES, {})
    for dish, ids in state.get("review", {}).items():
        entry = links["dishes"][dish]
        accept = state.get("accept", {}).get(dish)
        have = [v["id"] for v in entry["videos"]]
        new = [v for v in ids if v not in have]
        if accept in new:  # the recipe's own video is listed first among the new ones
            new = [accept] + [v for v in new if v != accept]
        c = state["dishes"][dish]["candidates"]
        add = [
            {
                f: c[v][f]
                for f in ("id", "title", "channel", "thumbnail", "duration_s", "view_count")
            }
            for v in new
        ]
        room = max(KEEP - len(have), 0)
        if accept and accept in new and room == 0:
            room = 1  # the recipe's video must be stored; it replaces the last stored link
            entry["videos"] = entry["videos"][: KEEP - 1]
        entry["videos"] = entry["videos"] + add[:room]
        if add[:room]:
            entry["fetched_at"] = now_iso()
    for dish, vid in state.get("accept", {}).items():
        recipes["recipes"][dish] = state["dishes"][dish]["tries"][vid]["recipe"]
    for path, value in ((VERIFIED, links), (RECIPES, recipes)):
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        os.chmod(tmp, 0o600)
        tmp.replace(path)
    state["merged_at"] = now_iso()
    private(STATE, state)
    print("merged", {d: len(links["dishes"][d]["videos"]) for d in state.get("review", {})})


if __name__ == "__main__":
    stage = sys.argv[1]
    if stage in ("collect", "judge", "build") and "--live" not in sys.argv:
        raise SystemExit("pass --live")
    rest = sys.argv[2:]
    if "--root" in rest:
        i = rest.index("--root")
        rest = rest[:i] + rest[i + 2 :]
    args = [a for a in rest if a != "--live"]
    if stage == "build":
        build(args[0], args[1:])
    else:
        {"collect": collect, "judge": judge, "show": show, "merge": merge}[stage]()
