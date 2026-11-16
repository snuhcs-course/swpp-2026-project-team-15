# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Fill the server's YouTube video cache for the baseline dishes.

Dry run by default: prints how many requests and quota units a live run would use.
A live run needs a YouTube Data API key (YOUTUBE_API_KEY, or ~/.config/mylittlechef/youtube.env)
and writes the cache file given by --cache or DISH_VIDEO_CACHE.

    python scripts/youtube_prefetch.py --cache data/dish-videos.json
    python scripts/youtube_prefetch.py --cache data/dish-videos.json --live --max-requests 40

Quota estimate: 100 units per search and 1 per video lookup (default daily quota 10,000).
Check the YouTube API terms before keeping cached data.
"""

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "server"))

from app.dishes.catalog import Catalog  # noqa: E402
from app.dishes.youtube import CACHE_ENV, VideoCache, YouTubeClient, prefetch  # noqa: E402

KEY_FILE = Path.home() / ".config" / "mylittlechef" / "youtube.env"


def read_key() -> str:
    key = os.environ.get("YOUTUBE_API_KEY", "")
    if not key and KEY_FILE.is_file():
        for line in KEY_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("YOUTUBE_API_KEY="):
                key = line.split("=", 1)[1].strip()
    return key


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--cache", help=f"cache file (default: ${CACHE_ENV})")
    p.add_argument("--live", action="store_true", help="call the YouTube API (needs a key)")
    p.add_argument("--max-requests", type=int, default=40, help="API request cap for this run")
    p.add_argument("--max-age-days", type=int, default=7, help="skip dishes fetched more recently")
    p.add_argument("--force", action="store_true", help="refetch even fresh entries")
    p.add_argument("--only", nargs="*", help="dish ids to fetch (default: all)")
    args = p.parse_args(argv)

    cache = VideoCache(args.cache)
    if cache.path is None:
        p.error(f"give --cache or set {CACHE_ENV}")
    dishes = [(d.id, d.name) for d in Catalog.load().dishes.values()]
    if args.only:
        dishes = [x for x in dishes if x[0] in set(args.only)]
    client = None
    if args.live:
        key = read_key()
        if not key:
            p.error("--live needs YOUTUBE_API_KEY or ~/.config/mylittlechef/youtube.env")
        client = YouTubeClient(key)
    summary = prefetch(
        dishes,
        cache,
        client,
        max_requests=args.max_requests,
        max_age_days=args.max_age_days,
        force=args.force,
    )
    mode = "live" if args.live else "dry run (nothing was requested)"
    print(f"{mode}: {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
