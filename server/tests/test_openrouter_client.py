# AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
"""The shared OpenRouter client: OpenRouter's base URL, no SDK retries, no redirects, key in a
header only."""

import httpx
import openai
import pytest

from app.openrouter import OPENROUTER_BASE_URL, openrouter_client


def test_client_targets_openrouter_without_sdk_retries_or_redirects():
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(429, json={"error": {"message": "slow down"}})

    client = openrouter_client("secret-key", timeout=5, transport=httpx.MockTransport(handler))
    assert str(client.base_url).rstrip("/") == OPENROUTER_BASE_URL and client.max_retries == 0
    with pytest.raises(openai.RateLimitError):
        client.chat.completions.create(model="m", messages=[{"role": "user", "content": "x"}])
    assert len(seen) == 1  # the server's own retry decides, not the SDK
    request = seen[0]
    assert request.url == f"{OPENROUTER_BASE_URL}/chat/completions"
    assert "secret-key" not in str(request.url)
    assert request.headers["authorization"] == "Bearer secret-key"


def test_a_blank_key_is_refused():
    with pytest.raises(ValueError):
        openrouter_client("  ", timeout=5)
