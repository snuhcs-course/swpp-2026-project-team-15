# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Minimal YouTube Data API v3 client (search.list, videos.list) used by the discovery studies.

The server no longer searches YouTube (see server/app/dishes/videos.py); the studies keep this
client so their runners stay reproducible. The key is never logged.
"""

import httpx

API = "https://www.googleapis.com/youtube/v3"


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

    def search(self, query: str, max_results: int = 25) -> list[str]:
        data = self._get(
            "search",
            {
                "part": "id",
                "type": "video",
                "order": "relevance",
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
