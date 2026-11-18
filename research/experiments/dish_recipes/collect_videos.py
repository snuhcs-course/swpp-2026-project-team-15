# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
"""Stage A: one on-demand video lookup per dish, saved as a snapshot.

Reuses the server's `VideoFinder` (model proposal, then one batched YouTube lookup that keeps
existing, public, embeddable videos in the model's order). A second lookup adds running time and
view counts of the kept videos. Dry run unless `--allow-live-api` is given.

    cd server && PYTHONPATH=.:../research uv run python -m experiments.dish_recipes.collect_videos \
        --allow-live-api [--only kimchi-fried-rice ...] [--force]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time

import httpx

from app.dishes.catalog import Catalog
from app.dishes.videos import YOUTUBE_VIDEOS, VideoError, VideoFinder

from .common import VIDEOS_FILE, load_json, now_iso, read_key, save_json

DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")
MAX_MODEL_CALLS = 160
MAX_COST_USD = 1.5
FALLBACK_COST_PER_CALL = 0.0075  # measured in an earlier round, used when usage is missing


def parse_duration(iso: str) -> int:
    match = DURATION_RE.fullmatch(iso or "")
    if not match:
        return 0
    hours, minutes, seconds = (int(part or 0) for part in match.groups())
    return hours * 3600 + minutes * 60 + seconds


class CountingTransport(httpx.HTTPTransport):
    """Counts requests per host and sums the cost the model service reports."""

    def __init__(self):
        super().__init__()
        self.model_calls = 0
        self.youtube_calls = 0
        self.cost_usd = 0.0

    def handle_request(self, request):
        response = super().handle_request(request)
        host = request.url.host
        if host == "openrouter.ai":
            self.model_calls += 1
            response.read()
            try:
                self.cost_usd += float(response.json().get("usage", {}).get("cost") or 0)
            except (ValueError, TypeError, AttributeError):
                self.cost_usd += FALLBACK_COST_PER_CALL
        elif host.endswith("googleapis.com"):
            self.youtube_calls += 1
        return response


def details(youtube_key: str, ids: list[str], transport) -> dict[str, dict]:
    """Running time (seconds) and view count per video id, one batched lookup."""
    params = {"part": "contentDetails,statistics", "id": ",".join(ids)}
    with httpx.Client(timeout=20, transport=transport) as client:
        response = client.get(
            YOUTUBE_VIDEOS, params=params, headers={"X-Goog-Api-Key": youtube_key}
        )
    if response.status_code != 200:
        return {}
    out = {}
    for item in response.json().get("items", []):
        views = item.get("statistics", {}).get("viewCount")
        out[item["id"]] = {
            "duration_s": parse_duration(item.get("contentDetails", {}).get("duration", "")),
            "view_count": int(views) if views else None,
        }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--allow-live-api", action="store_true")
    parser.add_argument("--only", nargs="*", default=[])
    parser.add_argument("--force", action="store_true", help="fetch again even if saved")
    args = parser.parse_args(argv)

    dishes = [d for d in Catalog.load().dishes.values() if not args.only or d.id in args.only]
    snapshot = load_json(VIDEOS_FILE, {"schema": 1, "dishes": {}})
    todo = [d for d in dishes if args.force or d.id not in snapshot["dishes"]]
    print(f"{len(dishes)} dishes, {len(todo)} to fetch (limit {MAX_MODEL_CALLS} model calls)")
    if not args.allow_live_api:
        print("dry run: add --allow-live-api to call the model and YouTube")
        return 0
    openrouter, youtube = (
        read_key("OPENROUTER_API_KEY", "openrouter.env"),
        read_key("YOUTUBE_API_KEY", "youtube.env"),
    )
    if not openrouter or not youtube:
        print("missing key file in ~/.config/mylittlechef", file=sys.stderr)
        return 2
    transport = CountingTransport()
    finder = VideoFinder(openrouter, youtube, transport=transport)
    failures: dict[str, str] = {}
    for dish in todo:
        if transport.model_calls >= MAX_MODEL_CALLS or transport.cost_usd >= MAX_COST_USD:
            print("budget reached, stopping")
            break
        try:
            videos = finder.find(dish.id, dish.name)
            extra = details(youtube, [v.video_id for v in videos], transport) if videos else {}
        except VideoError as error:
            failures[dish.id] = str(error)
            print(f"  {dish.id}: FAILED ({error})")
            continue
        snapshot["dishes"][dish.id] = {
            "fetched_at": now_iso(),
            "videos": [
                {
                    "id": v.video_id,
                    "title": v.title,
                    "channel": v.channel,
                    "thumbnail": v.thumbnail_url,
                    **extra.get(v.video_id, {}),
                }
                for v in videos
            ],
        }
        save_json(VIDEOS_FILE, snapshot)
        print(f"  {dish.id}: {len(videos)} videos")
        time.sleep(0.5)
    print(
        json.dumps(
            {
                "model_calls": transport.model_calls,
                "youtube_calls": transport.youtube_calls,
                "cost_usd": round(transport.cost_usd, 4),
                "failures": failures,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
