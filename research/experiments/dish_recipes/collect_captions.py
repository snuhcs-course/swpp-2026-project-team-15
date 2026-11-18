# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
"""Stage B: caption text for the first usable video of each dish (unofficial route).

For each dish, goes through its saved videos in the model's order (at most four) until one has
captions, waits 2 s between requests and stops on the first sign of blocking. Writes one input file
per dish under data/dish-recipes/inputs/ plus _missing.json. Run through `uv run --with
youtube-transcript-api`; dry run unless `--allow-network`.

    cd server && PYTHONPATH=.:../research uv run --with youtube-transcript-api \
        python -m experiments.dish_recipes.collect_captions --allow-network
"""

from __future__ import annotations

import argparse
import sys
import time

from app.dishes.catalog import Catalog

from .captions import Blocked, fetch_transcript
from .common import INPUTS_DIR, MISSING_FILE, VIDEOS_FILE, load_json, save_json

MAX_TRIES = 4
PAUSE_S = 2.0


def input_record(dish, video: dict, transcript) -> dict:
    return {
        "dish": {"id": dish.id, "name": dish.name, "category": dish.category},
        "video": {
            "id": video["id"],
            "title": video["title"],
            "channel": video["channel"],
            "duration_s": video.get("duration_s"),
            "language": transcript.language,
            "caption_kind": transcript.kind,
        },
        "transcript": transcript.snippets,
        "caption_chars": transcript.chars,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--allow-network", action="store_true")
    parser.add_argument("--only", nargs="*", default=[])
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    snapshot = load_json(VIDEOS_FILE, {"dishes": {}})["dishes"]
    catalog = Catalog.load()
    dishes = [d for d in catalog.dishes.values() if not args.only or d.id in args.only]
    missing = load_json(MISSING_FILE, {})
    todo = [
        d
        for d in dishes
        if d.id in snapshot
        and (args.force or not (INPUTS_DIR / f"{d.id}.json").exists())
        and (args.force or d.id not in missing)
    ]
    print(f"{len(todo)} dishes to try")
    if not args.allow_network:
        print("dry run: add --allow-network to request captions")
        return 0
    for dish in todo:
        found = None
        tried = []
        for video in snapshot[dish.id]["videos"][:MAX_TRIES]:
            try:
                transcript = fetch_transcript(video["id"])
            except Blocked as reason:
                print(f"BLOCKED at {dish.id} ({reason}); stopping", file=sys.stderr)
                save_json(MISSING_FILE, missing)
                return 3
            tried.append(video["id"])
            time.sleep(PAUSE_S)
            if transcript:
                found = (video, transcript)
                break
        if found:
            save_json(INPUTS_DIR / f"{dish.id}.json", input_record(dish, *found))
            missing.pop(dish.id, None)
            print(f"  {dish.id}: {found[1].language} {found[1].kind} {found[1].chars} chars")
        else:
            missing[dish.id] = {"tried": tried}
            print(f"  {dish.id}: no captions in {len(tried)} videos")
        save_json(MISSING_FILE, missing)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
