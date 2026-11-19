# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""The one place that waits and tries again when the model service limits a burst of calls."""

import time
from collections.abc import Callable

import httpx

RETRY_WAITS = (3, 8)  # seconds before the first and the second retry after a 429


def post_with_retry(
    client: httpx.Client,
    url: str,
    payload: dict,
    headers: dict[str, str],
    *,
    waits: tuple[float, ...] = RETRY_WAITS,
    sleep: Callable[[float], None] = time.sleep,
) -> httpx.Response:
    """The waits and the sleep are handed in, so a test passes (0, 0) instead of patching."""
    response = client.post(url, json=payload, headers=headers)
    for wait in waits:
        if response.status_code != 429:
            break
        sleep(wait)
        response = client.post(url, json=payload, headers=headers)
    return response
