# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.

# Modified by Codex (GPT-6.1 Sol), 2026-11-21; reviewed by Soohyun An
# Changes: inject clock to exclude checkpoint overhead
"""One bounded OpenRouter text call with a strict JSON schema; no secret-bearing errors."""

import json
import logging
import time
from collections.abc import Callable

import httpx

from app.dishes.errors import DishLLMError
from app.dishes.http import APP_READ_SECONDS, RETRY_WAITS, post_with_retry
from app.dishes.youtube import YOUTUBE_TIMEOUT
from app.json_lists import salvage_list

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-2.5-flash-lite"
MAX_TOKENS = 4096
CALL_TIMEOUT = 30.0  # seconds for one attempt
# The longest route is a revision: a YouTube credit lookup, then up to two model calls. Each
# call, retries included, therefore fits in half of what is left of the app's wait.
CALL_BUDGET = (APP_READ_SECONDS - YOUTUBE_TIMEOUT) / 2
log = logging.getLogger(__name__)


class DishLLM:
    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        *,
        transport=None,
        retry_waits: tuple[float, ...] = RETRY_WAITS,
        clock: Callable[[], float] = time.monotonic,
    ):
        if not api_key.strip():
            raise ValueError("an API key is required")
        self._api_key = api_key
        self._model = model
        self._transport = transport
        self._retry_waits = retry_waits
        # Research tracing can exclude checkpoint I/O from the shared policy clock.
        self._clock = clock

    def complete(
        self, system: str, user: str, name: str, schema: dict, max_tokens: int | None = None
    ) -> dict:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": name, "strict": True, "schema": schema},
            },
            "provider": {"require_parameters": True},
            "max_tokens": max_tokens or MAX_TOKENS,
            "temperature": 0,
        }
        started = self._clock()
        try:
            with httpx.Client(
                timeout=CALL_TIMEOUT, transport=self._transport, follow_redirects=False
            ) as client:
                headers = {"Authorization": f"Bearer {self._api_key}"}
                response = post_with_retry(
                    client,
                    ENDPOINT,
                    payload,
                    headers,
                    waits=self._retry_waits,
                    budget=CALL_BUDGET,
                    clock=self._clock,
                )
            if response.status_code == 429 or response.status_code >= 500:
                raise DishLLMError("The model service is temporarily unavailable")
            if response.status_code != 200:
                raise DishLLMError("The model service rejected the request")
            body = response.json()
            choice = body["choices"][0]
            usage = body.get("usage") or {}
            log.info(
                "dish model call %s: %.1fs, finish=%s, tokens in=%s out=%s",
                name,
                self._clock() - started,
                choice.get("finish_reason"),
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
            )
            message = choice["message"]
            if message.get("refusal"):
                raise DishLLMError("The model returned an incomplete answer")
            if choice.get("finish_reason") == "length":
                data = salvage_list(message.get("content") or "")
                if data is None:
                    raise DishLLMError("The model returned an incomplete answer")
                log.warning("dish model call %s was cut at the token limit", name)
            elif choice.get("finish_reason") != "stop":
                raise DishLLMError("The model returned an incomplete answer")
            else:
                data = json.loads(message["content"])
        except (httpx.TimeoutException, httpx.TransportError):
            raise DishLLMError("The model service could not be reached") from None
        except (ValueError, KeyError, TypeError, IndexError):
            raise DishLLMError("The model returned an invalid answer") from None
        if not isinstance(data, dict):
            raise DishLLMError("The model returned an invalid answer")
        return data
