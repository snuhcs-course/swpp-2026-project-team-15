# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Fill dishes still without a verified link from the official YouTube search.

The web-search model kept returning videos already rejected for these dishes, so this round
uses search.list (100 units per call, its own daily bucket) with the same exclusion of rejected
ids, the same two judges as ``verify_videos`` and a person's review in search order. Up to
``KEEP`` relevant videos are kept per dish in search order (no ranking by views).

Stages (run from ``server/`` with ``PYTHONPATH=.:../research``):
    search --allow-network [--alt]   one search.list call per dish ('<name> 레시피'; --alt uses
                                     '<name> 만들기' for dishes with no kept video yet)
    judge --allow-network            both judges on the new candidates, one batch per dish
    merge                            back up the verified file, then replace only these dishes
The review file ``review-search.json`` maps pair keys to {"decision", "reason"}.
"""

from __future__ import annotations

import argparse
import shutil

import httpx

from .common import DATA_DIR, load_json, now_iso, read_key, save_json
from .supplement_videos import EMPTY_DISHES, enrich, merged, new_ids, rejected, write_atomic
from .verify_videos import (
    JUDGE_PROMPT,
    JUDGES,
    REPORT,
    VERIFIED,
    chat,
    dish_table,
    item_text,
    parse_judgements,
    playable,
)

SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
SEARCH_UNITS = 100
KEEP = 5
WORDINGS = ("{name} 레시피", "{name} 만들기")
STATE = DATA_DIR / "search.json"
REVIEW = DATA_DIR / "review-search.json"
BACKUP = DATA_DIR / "dish-videos.verified.before-search.json"


def search_params(query: str) -> dict:
    return {
        "part": "snippet",
        "q": query,
        "type": "video",
        "relevanceLanguage": "ko",
        "regionCode": "KR",
        "order": "relevance",
        "maxResults": 25,
        "videoEmbeddable": "true",
    }


def result_ids(payload: dict) -> list[str]:
    """Video ids of a search.list response, in result order."""
    return [i["id"]["videoId"] for i in payload.get("items", []) if i.get("id", {}).get("videoId")]


def kept_in_order(order: list[str], review: dict[str, dict], dish_id: str, keep: int) -> list[str]:
    """The first ``keep`` ids the reviewer marked relevant, in search order."""
    out = []
    for vid in order:
        r = review.get(f"{dish_id}|{vid}")
        if r and r["decision"] == "relevant":
            out.append(vid)
            if len(out) == keep:
                break
    return out


def cmd_search(alt: bool) -> None:
    key = read_key("YOUTUBE_API_KEY", "youtube.env")
    state = load_json(STATE, {"dishes": {}, "units": 0})
    report, table, review = load_json(REPORT, {}), dish_table(), load_json(REVIEW, {})
    wording = WORDINGS[1 if alt else 0]
    for dish_id in EMPTY_DISHES:
        entry = state["dishes"].setdefault(dish_id, {"searches": [], "order": [], "candidates": {}})
        if any(s["q"].endswith(wording.split()[-1]) for s in entry["searches"]):
            continue
        if alt and kept_in_order(entry["order"], review, dish_id, 1):
            continue
        query = wording.format(name=table[dish_id]["name"])
        r = httpx.get(
            SEARCH_URL, params=search_params(query), headers={"X-Goog-Api-Key": key}, timeout=30
        )
        state["units"] += SEARCH_UNITS
        if r.status_code != 200:
            entry["searches"].append(
                {"at": now_iso(), "q": query, "error": f"HTTP {r.status_code}"}
            )
            save_json(STATE, state)
            print(f"  {dish_id}: HTTP {r.status_code}; stopping")
            return
        ids = result_ids(r.json())
        seen = rejected(report, dish_id) | set(entry["order"])
        fresh = new_ids(ids, seen)
        details = enrich(key, fresh) if fresh else {}
        state["units"] += 1 if fresh else 0
        entry["searches"].append({"at": now_iso(), "q": query, "results": ids, "new": fresh})
        for vid in fresh:
            if playable(details.get(vid)):
                entry["order"].append(vid)
                entry["candidates"][vid] = details[vid]
        print(f"  {dish_id}: results {len(ids)}, new {len(fresh)}, playable {len(entry['order'])}")
        save_json(STATE, state)


def cmd_judge(models: tuple[str, ...] = JUDGES) -> None:
    key = read_key("OPENROUTER_API_KEY", "openrouter.env")
    state, table = load_json(STATE, {"dishes": {}}), dish_table()
    for dish_id, entry in state["dishes"].items():
        todo = [v for v in entry["order"] if f"{dish_id}|{v}" not in entry.setdefault("judged", {})]
        if not todo:
            continue
        keys = [f"{dish_id}|{v}" for v in todo]
        items = "\n".join(
            item_text(k, table[dish_id], entry["candidates"][v])
            for k, v in zip(keys, todo, strict=True)
        )
        for model in models:
            res = chat(key, model, JUDGE_PROMPT.format(items=items))
            parsed = parse_judgements(res.get("text", ""), keys) if "error" not in res else None
            state.setdefault("cost", 0.0)
            state["cost"] += res["cost"]
            state["calls"] = state.get("calls", 0) + res["calls"]
            for k in keys:
                entry["judged"].setdefault(k, {})[model] = (parsed or {}).get(k)
        save_json(STATE, state)
        print(f"  {dish_id}: judged {len(keys)}")


def cmd_merge() -> None:
    state, review = load_json(STATE, {"dishes": {}}), load_json(REVIEW, {})
    report, table = load_json(REPORT, {}), dish_table()
    additions: dict[str, list[dict]] = {}
    for dish_id in EMPTY_DISHES:
        entry = state["dishes"].get(dish_id, {"order": [], "candidates": {}, "judged": {}})
        keep = kept_in_order(entry["order"], review, dish_id, KEEP)
        for rank, vid in enumerate(entry["order"]):
            k, v = f"{dish_id}|{vid}", entry["candidates"][vid]
            report[k] = {
                "dish": dish_id,
                "dish_name": table[dish_id]["name"],
                "video": vid,
                "rank": rank,
                "playable": True,
                "title": v["title"],
                "channel": v["channel"],
                "judges": entry.get("judged", {}).get(k, {}),
                "queued": "search_api",
                "review": review.get(k),
                "keep": vid in keep,
                "basis": f"reviewer:{review[k]['decision']}" if k in review else "not_reached",
            }
        additions[dish_id] = [
            {
                f: entry["candidates"][v][f]
                for f in ("id", "title", "channel", "thumbnail", "duration_s", "view_count")
            }
            for v in keep
        ]
    if not BACKUP.exists():
        shutil.copy2(VERIFIED, BACKUP)
    write_atomic(VERIFIED, merged(load_json(VERIFIED, {}), additions, now_iso()))
    write_atomic(REPORT, report)
    print({d: len(v) for d, v in additions.items()})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("stage", choices=("search", "judge", "merge"))
    ap.add_argument("--allow-network", action="store_true")
    ap.add_argument("--alt", action="store_true")
    ap.add_argument(
        "--secondary-only",
        action="store_true",
        help="judge with the secondary model only (cost cap); a person reviews every candidate",
    )
    args = ap.parse_args(argv)
    if args.stage in ("search", "judge") and not args.allow_network:
        ap.error("this stage calls paid or quota-limited APIs; pass --allow-network")
    if args.stage == "search":
        cmd_search(args.alt)
    elif args.stage == "judge":
        cmd_judge(JUDGES[1:] if args.secondary_only else JUDGES)
    else:
        cmd_merge()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
