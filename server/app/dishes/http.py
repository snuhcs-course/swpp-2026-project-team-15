# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""The one place that waits and tries again when the model service limits a burst of calls."""

import time
from collections.abc import Callable

import httpx

RETRY_WAITS = (3, 8)  # seconds before the first and the second retry after a 429
# The app gives up on an answer after 90 s (DishApi.kt, readTimeout). Every route spends at most
# this long, so the server never keeps working, and paying, for an answer nobody reads.
APP_READ_SECONDS = 90.0


def post_with_retry(
    client: httpx.Client,
    url: str,
    payload: dict,
    headers: dict[str, str],
    *,
    waits: tuple[float, ...] = RETRY_WAITS,
    sleep: Callable[[float], None] = time.sleep,
    budget: float | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> httpx.Response:
    """The waits and the sleep are handed in, so a test passes (0, 0) instead of patching.

    With a ``budget`` (seconds for all attempts and waits together) a retry is made only when
    time is left after the wait, and every attempt may take only the time that is left."""
    started = clock()

    def left() -> float | None:
        return None if budget is None else budget - (clock() - started)

    response = _post(client, url, payload, headers, left())
    for wait in waits:
        if response.status_code != 429:
            break
        remaining = left()
        if remaining is not None and remaining - wait <= 0:
            break
        sleep(wait)
        response = _post(client, url, payload, headers, left())
    return response


def _post(client, url, payload, headers, remaining: float | None) -> httpx.Response:
    if remaining is None:
        return client.post(url, json=payload, headers=headers)
    timeout = min(remaining, client.timeout.read or remaining)
    return client.post(url, json=payload, headers=headers, timeout=timeout)
