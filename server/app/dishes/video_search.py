# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Ask a web-search model for YouTube videos to follow along and cook a dish.

The model only proposes ids; whether they can be shown is decided by the verifier (study:
research/experiments/dish_pipeline, round 3: no title filter, no sorting by views, no count limit).
"""

import re
import time
from collections.abc import Callable

import httpx
import openai
from openai.types.chat import ChatCompletion, ChatCompletionUserMessageParam

from app.dishes.errors import VideoError
from app.dishes.http import APP_READ_SECONDS, RETRY_WAITS, retry_while
from app.dishes.youtube import YOUTUBE_TIMEOUT
from app.openrouter import openrouter_client

# A video request may check stored videos, search, then check what was found: the search gets
# what is left of the app's wait after two YouTube checks. The slowest search recorded in the
# discovery study took 22.7 s (median 3.5 s).
SEARCH_BUDGET = APP_READ_SECONDS - 2 * YOUTUBE_TIMEOUT

WEB_MODEL = "google/gemini-2.5-flash-lite:online"
ID_RE = re.compile(r"(?:v=|youtu\.be/|/embed/|/shorts/)([A-Za-z0-9_-]{11})")
MAX_IDS = 12  # one videos.list call takes up to 50 ids; the model is asked for 8

# Round 3 wording (variant D0): videos to follow along and cook the dish, nothing else.
REQUEST = (
    "YouTube에서 '{dish}'를 보고 따라 하며 만들 수 있는 요리 영상"
    "(만드는 방법을 보여 주는 레시피 영상)을 최대 8개 찾아 주세요."
    " 한국어 영상뿐 아니라 어떤 언어의 영상이든 괜찮습니다."
    " 각 영상의 watch?v= 주소와 제목을 JSON 배열로만 답하고,"
    " 검색 결과에서 실제로 확인한 주소만 쓰세요."
)


def extract_ids(text: str, citation_urls: list[str]) -> list[str]:
    """Video ids from the answer text, then from the citations, in that order, without repeats."""
    seen: dict[str, None] = {}
    for chunk in [text, *citation_urls]:
        for vid in ID_RE.findall(chunk or ""):
            seen.setdefault(vid)
    return list(seen)[:MAX_IDS]


def video_messages(dish_name: str) -> list[ChatCompletionUserMessageParam]:
    return [{"role": "user", "content": REQUEST.format(dish=dish_name)}]


class WebSearchVideoSource:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = WEB_MODEL,
        transport: httpx.BaseTransport | None = None,
        retry_waits: tuple[float, ...] = RETRY_WAITS,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._client = openrouter_client(api_key, timeout=SEARCH_BUDGET, transport=transport)
        self._api_key = api_key
        self._model = model
        self._retry_waits = retry_waits
        self._clock = clock  # handed in so a test can check the time each attempt gets

    def propose(self, dish_name: str) -> list[str]:
        def attempt(left: float | None) -> ChatCompletion | None:
            """None after a rate limit, so the retry waits and tries again."""
            try:
                return self._client.chat.completions.create(
                    model=self._model,
                    temperature=0,
                    messages=video_messages(dish_name),
                    timeout=SEARCH_BUDGET if left is None else left,
                )
            except openai.RateLimitError:
                return None

        try:
            completion = retry_while(
                attempt,
                lambda r: r is None,
                waits=self._retry_waits,
                budget=SEARCH_BUDGET,
                clock=self._clock,
            )
            if completion is None:
                raise VideoError("The model service is temporarily unavailable")
            message = completion.choices[0].message
            citations = [
                getattr(getattr(a, "url_citation", None), "url", "") or ""
                for a in message.annotations or []
            ]
            return extract_ids(message.content or "", citations)
        except openai.APIStatusError:
            raise VideoError("The model service is temporarily unavailable") from None
        except (openai.APITimeoutError, openai.APIConnectionError):
            raise VideoError("The model service could not be reached") from None
        except (ValueError, KeyError, TypeError, IndexError, AttributeError):
            raise VideoError("The model returned an invalid answer") from None
