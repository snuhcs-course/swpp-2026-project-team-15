# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Ask YouTube which of some video ids exist, are public and can be embedded.

One batched ``videos.list`` call (about 1 quota unit) answers for up to 50 ids. The titles and
thumbnails come from that response, so a video that was renamed shows its current title.
"""

import httpx

from app.dishes.errors import VideoError
from app.dishes.schemas import Video

YOUTUBE_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"


def to_video(item: dict) -> Video | None:
    """None unless the video is public and can be embedded."""
    status = item.get("status", {})
    if not status.get("embeddable") or status.get("privacyStatus", "public") != "public":
        return None
    snippet = item.get("snippet", {})
    thumbs = snippet.get("thumbnails", {})
    thumb = (thumbs.get("medium") or thumbs.get("default") or {}).get("url")
    return Video(
        video_id=item["id"],
        title=snippet.get("title", ""),
        channel=snippet.get("channelTitle", ""),
        thumbnail_url=thumb or f"https://i.ytimg.com/vi/{item['id']}/mqdefault.jpg",
    )


class YouTubeVerifier:
    def __init__(self, api_key: str, *, transport=None):
        if not api_key.strip():
            raise ValueError("a YouTube API key is required")
        self._api_key = api_key
        self._transport = transport

    def check(self, ids: list[str]) -> list[Video]:
        """The usable videos among ``ids``, in the order of ``ids``."""
        params = {"part": "snippet,status", "id": ",".join(ids)}
        headers = {"X-Goog-Api-Key": self._api_key}  # a header keeps the key out of URL logs
        try:
            with httpx.Client(timeout=20, transport=self._transport) as client:
                response = client.get(YOUTUBE_VIDEOS, params=params, headers=headers)
            if response.status_code != 200:
                raise VideoError(f"YouTube returned HTTP {response.status_code}")
            items = {i["id"]: i for i in response.json().get("items", [])}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise VideoError("YouTube could not be reached") from None
        return [v for vid in ids if vid in items and (v := to_video(items[vid]))]
