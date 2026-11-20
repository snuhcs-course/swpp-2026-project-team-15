# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Find new verified links for dishes that lost every link in the verification.

Same discovery request and the same two judges as ``collect_videos`` and ``verify_videos``;
video ids already rejected for a dish are skipped. A person reviews every judged pair
(``review-supplement.json``: pair key -> {"decision": "relevant"|"irrelevant"|"unsure",
"reason": ...}) before ``merge`` writes the kept videos into the verified file.

Stages (run from ``server/`` with ``PYTHONPATH=.:../research``):
    discover --allow-network   one discovery round for the dishes still without new candidates
    judge --allow-network      both judges on the new candidates
    merge                      back up the verified file, then replace only these dishes
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile

import httpx

from app.dishes.videos import VideoError, VideoFinder

from .common import DATA_DIR, load_json, now_iso, read_key, save_json
from .verify_videos import (
    JUDGE_PROMPT,
    JUDGES,
    REPORT,
    VERIFIED,
    YT_URL,
    chat,
    dish_table,
    item_text,
    parse_judgements,
    playable,
    to_video,
)

EMPTY_DISHES = (
    "chicken-garlic",
    "rice-ball-egg",
    "can-mackerel-stew",
    "kimchi-bibimbap",
    "kimchi-rolled",
    "pork-kimchi-fried-rice",
    "pork-lettuce",
    "tteok-ramyeon",
    "dumpling-ramyeon",
    "mushroom-porridge",
    "pork-belly-kimchi",
    "hotdog-pan",
    "pork-bowl",
    "tuna-fried-rice",
    "cheese-tteokbokki",
)
MAX_ROUNDS = 2
STATE = DATA_DIR / "supplement.json"
REVIEW = DATA_DIR / "review-supplement.json"
BACKUP = DATA_DIR / "dish-videos.verified.before-supplement.json"


def rejected(report: dict, dish_id: str) -> set[str]:
    """Video ids already judged for this dish (kept ones are not candidates either)."""
    return {p["video"] for p in report.values() if p["dish"] == dish_id}


def new_ids(proposed: list[str], seen: set[str]) -> list[str]:
    """Proposed ids not seen before, in the model's order, without duplicates."""
    out: list[str] = []
    for i in proposed:
        if i not in seen and i not in out:
            out.append(i)
    return out


def merged(verified: dict, additions: dict[str, list[dict]], fetched_at: str) -> dict:
    """The verified file with only the given dishes replaced."""
    dishes = dict(verified["dishes"])
    for dish_id, videos in additions.items():
        dishes[dish_id] = {"fetched_at": fetched_at, "videos": videos}
    return {**verified, "dishes": dishes}


def write_atomic(path, data: dict) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)


def enrich(key: str, ids: list[str]) -> dict[str, dict]:
    r = httpx.get(
        YT_URL,
        params={"part": "snippet,contentDetails,statistics,status", "id": ",".join(ids)},
        headers={"X-Goog-Api-Key": key},
        timeout=30,
    )
    r.raise_for_status()
    return {i["id"]: to_video(i) for i in r.json().get("items", [])}


def cmd_discover() -> None:
    openrouter, youtube = (
        read_key("OPENROUTER_API_KEY", "openrouter.env"),
        read_key("YOUTUBE_API_KEY", "youtube.env"),
    )
    state = load_json(STATE, {"dishes": {}, "units": 0})
    report, table = load_json(REPORT, {}), dish_table()
    for dish_id in EMPTY_DISHES:
        entry = state["dishes"].setdefault(dish_id, {"rounds": [], "candidates": {}})
        if len(entry["rounds"]) >= MAX_ROUNDS or entry["candidates"]:
            continue
        finder = VideoFinder(openrouter, youtube)  # fresh object: no cached answer
        try:
            videos = finder.find(dish_id, table[dish_id]["name"])
        except VideoError as error:
            entry["rounds"].append({"at": now_iso(), "error": str(error)})
            continue
        seen = rejected(report, dish_id) | set(entry["candidates"])
        fresh = new_ids([v.video_id for v in videos], seen)
        details = enrich(youtube, fresh) if fresh else {}
        state["units"] += 1 if fresh else 0
        entry["rounds"].append(
            {"at": now_iso(), "proposed": [v.video_id for v in videos], "new": fresh}
        )
        entry["candidates"].update({i: details[i] for i in fresh if playable(details.get(i))})
        print(
            f"  {dish_id}: proposed {len(videos)}, new {len(fresh)}, playable "
            f"{sum(playable(details.get(i)) for i in fresh)}"
        )
        save_json(STATE, state)


def cmd_judge() -> None:
    key = read_key("OPENROUTER_API_KEY", "openrouter.env")
    state, table = load_json(STATE, {"dishes": {}}), dish_table()
    for dish_id, entry in state["dishes"].items():
        cands = entry["candidates"]
        if not cands or entry.get("judges"):
            continue
        keys = [f"{dish_id}|{i}" for i in cands]
        items = "\n".join(
            item_text(k, table[dish_id], v) for k, v in zip(keys, cands.values(), strict=True)
        )
        entry["judges"] = {}
        for model in JUDGES:
            res = chat(key, model, JUDGE_PROMPT.format(items=items))
            parsed = parse_judgements(res.get("text", ""), keys) if "error" not in res else None
            entry["judges"][model] = {
                "judgements": parsed,
                "calls": res["calls"],
                "cost": res["cost"],
                "error": res.get("error") or (None if parsed else "unparsable"),
            }
        save_json(STATE, state)


def cmd_merge() -> None:
    state, review = load_json(STATE, {"dishes": {}}), load_json(REVIEW, {})
    report = load_json(REPORT, {})
    table = dish_table()
    additions: dict[str, list[dict]] = {}
    for dish_id in EMPTY_DISHES:
        entry = state["dishes"].get(dish_id, {"candidates": {}})
        kept = []
        for rank, (vid, v) in enumerate(entry["candidates"].items()):
            k = f"{dish_id}|{vid}"
            r = review.get(k)
            keep = bool(r and r["decision"] == "relevant")
            judges = {
                m: ((entry.get("judges", {}).get(m) or {}).get("judgements") or {}).get(k, {})
                for m in JUDGES
            }
            report[k] = {
                "dish": dish_id,
                "dish_name": table[dish_id]["name"],
                "video": vid,
                "rank": rank,
                "playable": True,
                "title": v["title"],
                "channel": v["channel"],
                "judges": judges,
                "queued": "supplement_all",
                "review": r,
                "keep": keep,
                "basis": f"reviewer:{r['decision']}" if r else "unreviewed",
            }
            if keep:
                kept.append(
                    {
                        f: v[f]
                        for f in ("id", "title", "channel", "thumbnail", "duration_s", "view_count")
                    }
                )
        additions[dish_id] = kept
    if not BACKUP.exists():
        shutil.copy2(VERIFIED, BACKUP)
    write_atomic(VERIFIED, merged(load_json(VERIFIED, {}), additions, now_iso()))
    write_atomic(REPORT, report)
    print({d: len(v) for d, v in additions.items()})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stage", choices=("discover", "judge", "merge"))
    ap.add_argument("--allow-network", action="store_true")
    args = ap.parse_args(argv)
    if args.stage in ("discover", "judge") and not args.allow_network:
        print("dry run: add --allow-network")
        return 0
    {"discover": cmd_discover, "judge": cmd_judge, "merge": cmd_merge}[args.stage]()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
