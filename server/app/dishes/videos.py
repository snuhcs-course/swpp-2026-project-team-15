# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""The videos of one dish: stored first, found by a model when nothing usable is stored.

Stored videos (see video_store.py) are served after the verifier has confirmed that they still
exist, are public and can be embedded. Only when nothing usable is stored does the source (a
web-search model) propose videos, which the same verifier checks. Found videos are kept in memory
for a day, and so is an empty finding, so a dish whose search found nothing playable does not
call the paid model on every tap. The check of stored videos is kept for ``check_seconds`` so
repeated taps cannot spend the daily YouTube quota (server review, 2026-11-19).
"""

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime

from app.dishes.errors import VideoError
from app.dishes.roles import StoredVideos, VideoSource, VideoVerifier
from app.dishes.schemas import Video

CACHE_SECONDS = 24 * 3600
YOUTUBE_DAILY_UNITS = 10_000  # default Data API quota; one videos.list call costs one unit
DAY_SECONDS = 24 * 3600


def check_seconds(dishes: int, recipe_videos: int, daily_units: int = YOUTUBE_DAILY_UNITS) -> float:
    """How long to reuse a check of stored videos so that checking every dish once per period,
    plus one credit lookup per recipe video a day (recipes.py), stays within the daily quota."""
    spare = daily_units - recipe_videos
    if dishes <= 0:
        return 0.0
    if spare <= 0:
        return float(DAY_SECONDS)
    return min(float(DAY_SECONDS), dishes * DAY_SECONDS / spare)


NOT_CONFIGURED = "Video search is not configured on this server"
log = logging.getLogger(__name__)


class VideoCache:
    """Videos found for a dish, kept for a day. One instance is made at app start."""

    def __init__(self, *, clock: Callable[[], float] = time.monotonic, ttl: float = CACHE_SECONDS):
        self._clock = clock
        self._ttl = ttl
        self._entries: dict[str, tuple[float, list[Video]]] = {}

    def get(self, dish_id: str) -> list[Video] | None:
        entry = self._entries.get(dish_id)
        if entry and self._clock() - entry[0] < self._ttl:
            return entry[1]
        return None

    def put(self, dish_id: str, videos: list[Video]) -> None:
        self._entries[dish_id] = (self._clock(), videos)


class VideoFinder:
    def __init__(
        self,
        verifier: VideoVerifier,
        stored: StoredVideos,
        cache: VideoCache,
        source: VideoSource | None = None,
        *,
        checked: VideoCache | None = None,
        now: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self._verifier = verifier
        self._stored = stored
        self._cache = cache
        self._source = source
        self._checked = checked or VideoCache(ttl=0)
        self._now = now

    def first_stored_id(self, dish_id: str) -> str | None:
        """The first stored video of the dish, without checking it with YouTube."""
        stored = self._stored.fresh_ids(dish_id, self._now())
        return stored[0] if stored else None

    def lookup(self, dish_id: str, dish_name: str) -> tuple[list[Video], str]:
        """The videos and where they came from: "stored" or "discovered"."""
        stored = self._stored.fresh_ids(dish_id, self._now())
        if stored:
            videos = self._checked.get(dish_id)
            if videos is None:
                videos = self._verifier.check(stored)
                self._checked.put(dish_id, videos)
                log.info("dish videos %s: stored=%d kept=%d", dish_id, len(stored), len(videos))
            if videos:
                return videos, "stored"
        cached = self._cache.get(dish_id)
        if cached is not None:
            return cached, "discovered"
        if self._source is None:
            raise VideoError(NOT_CONFIGURED)
        started = time.monotonic()
        ids = self._source.propose(dish_name)
        videos = self._verifier.check(ids) if ids else []
        log.info(
            "dish videos %s: %.1fs, proposed=%d kept=%d",
            dish_id,
            time.monotonic() - started,
            len(ids),
            len(videos),
        )
        self._cache.put(dish_id, videos)  # an empty finding too: no paid search on every tap
        return videos, "discovered"
