# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Orientation (vertical, horizontal, square) of stored videos from the official Data API.

The Data API has no "is a Short" field. ``videos.list`` with ``part=player`` and ``maxWidth``
returns ``player.embedWidth``/``embedHeight`` scaled to that width with the video's aspect ratio
kept (Data API reference, videos resource, player.embedHeight), so the ratio of the two tells the
orientation. One call covers 50 ids (1 quota unit).

    python -m experiments.dish_recipes.orientation --videos FILE --recipes FILE \
        --out FILE --allow-network
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Iterable, Sequence
from pathlib import Path

import httpx

from .common import read_key, save_json

API = "https://www.googleapis.com/youtube/v3/videos"
MAX_WIDTH = 1000  # any width works; the API keeps the aspect ratio


def orientation(width: int | str | None, height: int | str | None) -> str:
    """The API returns the embed size as strings ("1000", "563"); compare them as numbers."""
    try:
        width, height = int(width or 0), int(height or 0)
    except (TypeError, ValueError):
        return "unknown"
    if not width or not height:
        return "unknown"
    if height > width:
        return "vertical"
    if width > height:
        return "horizontal"
    return "square"


def batches(ids: Sequence[str], size: int = 50) -> Iterable[list[str]]:
    for start in range(0, len(ids), size):
        yield list(ids[start : start + size])


def fetch(ids: Sequence[str], key: str, client: httpx.Client) -> dict[str, str]:
    found: dict[str, str] = {}
    for batch in batches(ids):
        response = client.get(
            API,
            params={"part": "player", "maxWidth": MAX_WIDTH, "id": ",".join(batch)},
            headers={"X-Goog-Api-Key": key},
        )
        response.raise_for_status()
        for item in response.json().get("items", []):
            player = item.get("player", {})
            found[item["id"]] = orientation(player.get("embedWidth"), player.get("embedHeight"))
    return {vid: found.get(vid, "unknown") for vid in ids}


def summarize(dishes: dict, recipes: dict, by_id: dict[str, str]) -> dict:
    links = [v["id"] for entry in dishes.values() for v in entry["videos"]]
    counts: dict[str, int] = {}
    for vid in links:
        counts[by_id.get(vid, "unknown")] = counts.get(by_id.get(vid, "unknown"), 0) + 1
    first_vertical = sorted(
        dish
        for dish, entry in dishes.items()
        if entry["videos"] and by_id.get(entry["videos"][0]["id"]) == "vertical"
    )
    per_dish = {
        dish: sum(by_id.get(v["id"]) == "vertical" for v in entry["videos"])
        for dish, entry in dishes.items()
    }
    only_vertical = sorted(
        dish
        for dish, entry in dishes.items()
        if entry["videos"] and per_dish[dish] == len(entry["videos"])
    )
    recipe_vertical = sorted(
        dish for dish, recipe in recipes.items() if by_id.get(recipe["video"]["id"]) == "vertical"
    )
    return {
        "links": len(links),
        "distinct_videos": len(set(links)),
        "links_by_orientation": counts,
        "distinct_vertical": sum(1 for vid in set(links) if by_id.get(vid) == "vertical"),
        "dishes": len(dishes),
        "dishes_first_link_vertical": first_vertical,
        "dishes_only_vertical": only_vertical,
        "vertical_links_per_dish": per_dish,
        "recipes": len(recipes),
        "recipes_from_vertical": recipe_vertical,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--videos", type=Path, required=True)
    parser.add_argument("--recipes", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--allow-network", action="store_true")
    args = parser.parse_args(argv)
    dishes = json.loads(args.videos.read_text(encoding="utf-8"))["dishes"]
    recipes = json.loads(args.recipes.read_text(encoding="utf-8"))["recipes"]
    ids = sorted(
        {v["id"] for e in dishes.values() for v in e["videos"]}
        | {r["video"]["id"] for r in recipes.values()}
    )
    if not args.allow_network:
        print(f"dry run: {len(ids)} ids, {len(list(batches(ids)))} videos.list calls")
        return 0
    with httpx.Client(timeout=30) as client:
        by_id = fetch(ids, read_key("YOUTUBE_API_KEY", "youtube.env"), client)
    summary = summarize(dishes, recipes, by_id)
    save_json(args.out, {"orientation": by_id, "summary": summary})
    print(
        json.dumps(
            {k: v for k, v in summary.items() if k != "vertical_links_per_dish"}, ensure_ascii=False
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
