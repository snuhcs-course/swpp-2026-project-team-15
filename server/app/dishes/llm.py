# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""One bounded OpenRouter text call with a strict JSON schema; no secret-bearing errors."""

import json
import logging
import time

import httpx

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "google/gemini-2.5-flash-lite"
MAX_TOKENS = 4096
log = logging.getLogger(__name__)


class DishLLMError(Exception):
    """The model call failed or returned unusable output (message is safe to show)."""


class DishLLM:
    def __init__(self, api_key: str, model: str = DEFAULT_MODEL, *, transport=None):
        if not api_key.strip():
            raise ValueError("an API key is required")
        self._api_key = api_key
        self._model = model
        self._transport = transport

    def complete(self, system: str, user: str, name: str, schema: dict) -> dict:
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
            "max_tokens": MAX_TOKENS,
            "temperature": 0,
        }
        started = time.monotonic()
        try:
            with httpx.Client(
                timeout=30, transport=self._transport, follow_redirects=False
            ) as client:
                response = client.post(
                    ENDPOINT, json=payload, headers={"Authorization": f"Bearer {self._api_key}"}
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
                time.monotonic() - started,
                choice.get("finish_reason"),
                usage.get("prompt_tokens"),
                usage.get("completion_tokens"),
            )
            if choice.get("finish_reason") != "stop" or choice["message"].get("refusal"):
                raise DishLLMError("The model returned an incomplete answer")
            data = json.loads(choice["message"]["content"])
        except (httpx.TimeoutException, httpx.TransportError):
            raise DishLLMError("The model service could not be reached") from None
        except (ValueError, KeyError, TypeError, IndexError):
            raise DishLLMError("The model returned an invalid answer") from None
        if not isinstance(data, dict):
            raise DishLLMError("The model returned an invalid answer")
        return data
