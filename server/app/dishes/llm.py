# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.

# Modified by Codex (GPT-6.1 Sol), 2026-11-21; reviewed by Soohyun An
# Changes: inject clock to exclude checkpoint overhead
"""One bounded OpenRouter text call with a strict JSON schema; no secret-bearing errors."""

import json
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx
import openai
from openai.types.chat import ChatCompletion

from app.dishes.errors import DishLLMError
from app.dishes.http import APP_READ_SECONDS, RETRY_WAITS, retry_while
from app.dishes.youtube import YOUTUBE_TIMEOUT
from app.json_lists import salvage_list
from app.openrouter import json_schema_format, openrouter_client

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
        transport: httpx.BaseTransport | None = None,
        retry_waits: tuple[float, ...] = RETRY_WAITS,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._client = openrouter_client(api_key, timeout=CALL_TIMEOUT, transport=transport)
        self._api_key = api_key
        self._model = model
        self._retry_waits = retry_waits
        # Research tracing can exclude checkpoint I/O from the shared policy clock.
        self._clock = clock

    def complete(
        self, system: str, user: str, name: str, schema: dict, max_tokens: int | None = None
    ) -> dict:
        started = time.monotonic()

        def attempt(left: float | None) -> ChatCompletion | None:
            """None after a rate limit, so the retry waits and tries again."""
            try:
                return self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    response_format=json_schema_format(name, schema),
                    max_tokens=max_tokens or MAX_TOKENS,
                    temperature=0,
                    extra_body={"provider": {"require_parameters": True}},
                    timeout=CALL_TIMEOUT if left is None else min(left, CALL_TIMEOUT),
                )
            except openai.RateLimitError:
                return None

        try:
            completion = retry_while(
                attempt,
                lambda r: r is None,
                waits=self._retry_waits,
                budget=CALL_BUDGET,
                clock=self._clock,
            )
            if completion is None:
                raise DishLLMError("The model service is temporarily unavailable")
            choice = completion.choices[0]
            usage = completion.usage
            log.info(
                "dish model call %s: %.1fs, finish=%s, tokens in=%s out=%s",
                name,
                time.monotonic() - started,
                choice.finish_reason,
                usage.prompt_tokens if usage else None,
                usage.completion_tokens if usage else None,
            )
            message = choice.message
            data: Any
            if message.refusal:
                raise DishLLMError("The model returned an incomplete answer")
            if choice.finish_reason == "length":
                data = salvage_list(message.content or "")
                if data is None:
                    raise DishLLMError("The model returned an incomplete answer")
                log.warning("dish model call %s was cut at the token limit", name)
            elif choice.finish_reason != "stop":
                raise DishLLMError("The model returned an incomplete answer")
            else:
                data = json.loads(message.content or "")
        except openai.APIStatusError as exc:
            if exc.status_code >= 500:
                raise DishLLMError("The model service is temporarily unavailable") from None
            raise DishLLMError("The model service rejected the request") from None
        except (openai.APITimeoutError, openai.APIConnectionError):
            raise DishLLMError("The model service could not be reached") from None
        except (ValueError, KeyError, TypeError, IndexError, AttributeError):
            raise DishLLMError("The model returned an invalid answer") from None
        if not isinstance(data, dict):
            raise DishLLMError("The model returned an invalid answer")
        return data
