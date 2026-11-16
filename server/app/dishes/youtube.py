# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""YouTube video info: an optional server-side cache and the prefetch that fills it.

The cache holds API data, which is subject to the YouTube API terms (check them, including how
long cached data may be kept). Entries older than max_age_days are ignored.
"""

import json
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus

import httpx

CACHE_ENV = "DISH_VIDEO_CACHE"
API = "https://www.googleapis.com/youtube/v3"
SEARCH_COST, VIDEOS_COST = 100, 1


def search_url(dish_name: str) -> str:
    return f"https://www.youtube.com/results?search_query={quote_plus(dish_name + ' 레시피')}"


class VideoCache:
    def __init__(self, path: Path | str | None = None, *, max_age_days: int = 30, now=None):
        raw = path or os.environ.get(CACHE_ENV)
        self.path = Path(raw) if raw else None
        self.max_age = timedelta(days=max_age_days)
        self._now = now or (lambda: datetime.now(UTC))
        self._data: dict = {}
        if self.path and self.path.is_file():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                self._data = loaded if isinstance(loaded, dict) else {}
            except (OSError, ValueError):
                self._data = {}

    def get(self, dish_id: str) -> list[dict]:
        entry = self._data.get(dish_id)
        if not isinstance(entry, dict):
            return []
        try:
            fetched = datetime.fromisoformat(entry["fetched_at"])
        except (KeyError, ValueError, TypeError):
            return []
        if self._now() - fetched > self.max_age:
            return []
        videos = entry.get("videos")
        return videos if isinstance(videos, list) else []

    def fresh(self, dish_id: str, days: int) -> bool:
        entry = self._data.get(dish_id)
        try:
            return self._now() - datetime.fromisoformat(entry["fetched_at"]) < timedelta(days=days)
        except (KeyError, ValueError, TypeError):
            return False

    def put(self, dish_id: str, videos: list[dict]) -> None:
        self._data[dish_id] = {"fetched_at": self._now().isoformat(), "videos": videos}

    def save(self) -> None:
        if not self.path:
            raise ValueError("no cache path configured")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.path)


class YouTubeError(Exception):
    pass


class YouTubeClient:
    """Minimal Data API v3 client (search.list then videos.list). The key is never logged."""

    def __init__(self, api_key: str, *, transport=None):
        if not api_key.strip():
            raise ValueError("an API key is required")
        self._key = api_key
        self._transport = transport
        self.requests = 0

    def _get(self, path: str, params: dict) -> dict:
        self.requests += 1
        try:
            with httpx.Client(timeout=20, transport=self._transport) as client:
                response = client.get(f"{API}/{path}", params={**params, "key": self._key})
        except httpx.HTTPError:
            raise YouTubeError("YouTube could not be reached") from None
        if response.status_code != 200:
            raise YouTubeError(f"YouTube returned HTTP {response.status_code}")
        return response.json()

    def search(self, query: str, max_results: int = 10) -> list[str]:
        data = self._get(
            "search",
            {
                "part": "id",
                "type": "video",
                "order": "viewCount",
                "videoEmbeddable": "true",
                "maxResults": max_results,
                "q": query,
                "regionCode": "KR",
                "relevanceLanguage": "ko",
            },
        )
        return [i["id"]["videoId"] for i in data.get("items", []) if "videoId" in i.get("id", {})]

    def details(self, ids: list[str]) -> list[dict]:
        data = self._get("videos", {"part": "snippet,statistics,status", "id": ",".join(ids)})
        return data.get("items", [])


def to_video(item: dict) -> dict | None:
    status = item.get("status", {})
    if not status.get("embeddable") or status.get("privacyStatus", "public") != "public":
        return None
    snippet = item.get("snippet", {})
    thumbs = snippet.get("thumbnails", {})
    thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url")
    views = item.get("statistics", {}).get("viewCount")
    return {
        "video_id": item["id"],
        "title": snippet.get("title", ""),
        "channel": snippet.get("channelTitle", ""),
        "view_count": int(views) if views is not None else None,
        "thumbnail_url": thumb or f"https://i.ytimg.com/vi/{item['id']}/mqdefault.jpg",
        "embeddable": True,
    }


def top_videos(client: YouTubeClient, dish_name: str, keep: int = 3) -> list[dict]:
    ids = client.search(f"{dish_name} 레시피")
    if not ids:
        return []
    videos = [v for item in client.details(ids) if (v := to_video(item))]
    videos.sort(key=lambda v: v["view_count"] or 0, reverse=True)
    return videos[:keep]


def prefetch(
    dishes: list[tuple[str, str]],
    cache: VideoCache,
    client: YouTubeClient | None,
    *,
    max_requests: int,
    max_age_days: int = 7,
    force: bool = False,
    log: Callable[[str], None] = print,
    sleep: Callable[[float], None] = time.sleep,
) -> dict:
    """Plan (client is None) or run the cache fill. Returns a summary dict."""
    todo = [(i, n) for i, n in dishes if force or not cache.fresh(i, max_age_days)]
    budget = max(0, max_requests // 2)
    planned = todo[:budget]
    summary = {
        "dishes_total": len(dishes),
        "to_fetch": len(todo),
        "will_fetch": len(planned),
        "requests": 2 * len(planned),
        "quota_units": (SEARCH_COST + VIDEOS_COST) * len(planned),
        "fetched": 0,
        "failed": 0,
    }
    if client is None:
        return summary
    for dish_id, name in planned:
        try:
            cache.put(dish_id, top_videos(client, name))
            summary["fetched"] += 1
        except YouTubeError as exc:
            summary["failed"] += 1
            log(f"{dish_id}: {exc}")
            if "HTTP 403" in str(exc):  # quota or key problem: stop instead of burning requests
                break
        sleep(0.2)
    if summary["fetched"]:
        cache.save()
    return summary
