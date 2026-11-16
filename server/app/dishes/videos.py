# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Video links for one dish, found when the user asks for them.

A web-search model proposes YouTube videos for the dish; one batched YouTube lookup keeps those
that exist, are public and can be embedded, in the model's order. There is no title filter, no
sorting by views and no count limit (study: research/experiments/dish_pipeline, round 3).
Results are kept in memory for a day; API data must not be cached longer than the YouTube terms
allow.
"""

import logging
import re
import time

import httpx

from app.dishes.schemas import Video

OPENROUTER = "https://openrouter.ai/api/v1/chat/completions"
YOUTUBE_VIDEOS = "https://www.googleapis.com/youtube/v3/videos"
WEB_MODEL = "google/gemini-2.5-flash-lite:online"
CACHE_SECONDS = 24 * 3600
ID_RE = re.compile(r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})")
MAX_IDS = 12  # one videos.list call takes up to 50 ids; the model is asked for 8
log = logging.getLogger(__name__)

# Round 3 wording (variant D0): videos to follow along and cook the dish, nothing else.
REQUEST = (
    "YouTube에서 '{dish}'를 보고 따라 하며 만들 수 있는 요리 영상"
    "(만드는 방법을 보여 주는 레시피 영상)을 최대 8개 찾아 주세요."
    " 한국어 영상뿐 아니라 어떤 언어의 영상이든 괜찮습니다."
    " 각 영상의 watch?v= 주소와 제목을 JSON 배열로만 답하고,"
    " 검색 결과에서 실제로 확인한 주소만 쓰세요."
)


class VideoError(Exception):
    """The model or YouTube call failed (message is safe to show)."""


def extract_ids(text: str, citation_urls: list[str]) -> list[str]:
    """Video ids from the answer text, then from the citations, in that order, without repeats."""
    seen: dict[str, None] = {}
    for chunk in [text, *citation_urls]:
        for vid in ID_RE.findall(chunk or ""):
            seen.setdefault(vid)
    return list(seen)[:MAX_IDS]


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


class VideoFinder:
    def __init__(
        self,
        openrouter_key: str,
        youtube_key: str,
        *,
        model: str = WEB_MODEL,
        transport=None,
        clock=time.monotonic,
    ):
        if not openrouter_key.strip() or not youtube_key.strip():
            raise ValueError("both API keys are required")
        self._openrouter_key = openrouter_key
        self._youtube_key = youtube_key
        self._model = model
        self._transport = transport
        self._clock = clock
        self._cache: dict[str, tuple[float, list[Video]]] = {}

    def find(self, dish_id: str, dish_name: str) -> list[Video]:
        cached = self._cache.get(dish_id)
        if cached and self._clock() - cached[0] < CACHE_SECONDS:
            return cached[1]
        started = time.monotonic()
        ids = self._propose(dish_name)
        videos = self._check(ids) if ids else []
        log.info(
            "dish videos %s: %.1fs, proposed=%d kept=%d",
            dish_id,
            time.monotonic() - started,
            len(ids),
            len(videos),
        )
        if videos:
            self._cache[dish_id] = (self._clock(), videos)
        return videos

    def _propose(self, dish_name: str) -> list[str]:
        payload = {
            "model": self._model,
            "temperature": 0,
            "messages": [{"role": "user", "content": REQUEST.format(dish=dish_name)}],
        }
        headers = {"Authorization": f"Bearer {self._openrouter_key}"}
        try:
            with httpx.Client(timeout=60, transport=self._transport) as client:
                response = client.post(OPENROUTER, json=payload, headers=headers)
                if response.status_code == 429:  # the provider limits bursts: one short retry
                    time.sleep(3)
                    response = client.post(OPENROUTER, json=payload, headers=headers)
            if response.status_code != 200:
                raise VideoError("The model service is temporarily unavailable")
            message = response.json()["choices"][0]["message"]
            citations = [
                (a.get("url_citation") or {}).get("url", "")
                for a in message.get("annotations") or []
            ]
            return extract_ids(message.get("content") or "", citations)
        except (httpx.TimeoutException, httpx.TransportError):
            raise VideoError("The model service could not be reached") from None
        except (ValueError, KeyError, TypeError, IndexError):
            raise VideoError("The model returned an invalid answer") from None

    def _check(self, ids: list[str]) -> list[Video]:
        params = {"part": "snippet,status", "id": ",".join(ids), "key": self._youtube_key}
        try:
            with httpx.Client(timeout=20, transport=self._transport) as client:
                response = client.get(YOUTUBE_VIDEOS, params=params)
            if response.status_code != 200:
                raise VideoError(f"YouTube returned HTTP {response.status_code}")
            items = {i["id"]: i for i in response.json().get("items", [])}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise VideoError("YouTube could not be reached") from None
        return [v for vid in ids if vid in items and (v := to_video(items[vid]))]
