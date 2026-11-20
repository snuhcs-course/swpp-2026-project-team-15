# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
"""The one place an OpenRouter client is made. OpenRouter speaks the OpenAI chat API, so every
model call (dish model, video search, photo recognition) uses the official openai SDK with
OpenRouter's base URL. The key travels in the Authorization header, never in a URL or a log."""

from typing import Any

import httpx
from openai import DefaultHttpxClient, OpenAI
from openai.types.shared_params import ResponseFormatJSONSchema

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


def openrouter_client(
    api_key: str, *, timeout: float, transport: httpx.BaseTransport | None = None
) -> OpenAI:
    """``max_retries=0``: the waits after a rate limit are the server's own (dishes/http.py).
    ``transport`` lets a test answer offline (httpx.MockTransport)."""
    if not api_key.strip():
        raise ValueError("an API key is required")
    http_client = DefaultHttpxClient(transport=transport, follow_redirects=False)
    return OpenAI(
        api_key=api_key,
        base_url=OPENROUTER_BASE_URL,
        timeout=timeout,
        max_retries=0,
        http_client=http_client,
    )


def json_schema_format(name: str, schema: dict[str, Any]) -> ResponseFormatJSONSchema:
    """Structured output: the answer must match ``schema`` exactly (strict)."""
    return {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}
