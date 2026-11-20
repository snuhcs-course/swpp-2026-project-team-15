# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
# Modified with Claude Code (Opus 5.5), 2026-11-20: the retry loop is tenacity's.
"""The one place that waits and tries again when the model service limits a burst of calls."""

import time
from collections.abc import Callable

from tenacity import (
    RetryCallState,
    Retrying,
    retry_if_result,
    stop_after_attempt,
    wait_chain,
    wait_fixed,
)

RETRY_WAITS = (3, 8)  # seconds before the first and the second retry after a 429
# The app gives up on an answer after 90 s (DishApi.kt, readTimeout). Every route spends at most
# this long, so the server never keeps working, and paying, for an answer nobody reads.
APP_READ_SECONDS = 90.0


def retry_while[T](
    attempt: Callable[[float | None], T],
    again: Callable[[T], bool],
    *,
    waits: tuple[float, ...] = RETRY_WAITS,
    sleep: Callable[[float], None] = time.sleep,
    budget: float | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> T:
    """Call ``attempt(seconds_left)`` until ``again(result)`` is false, waiting ``waits`` between
    tries. With a ``budget`` (seconds for all attempts and waits together) a retry is made only
    when time is left after the wait. The waits and the sleep are handed in, so a test passes
    (0, 0) or a fake sleep instead of patching."""
    started = clock()

    def left() -> float | None:
        return None if budget is None else budget - (clock() - started)

    tries = stop_after_attempt(len(waits) + 1)

    def stop(state: RetryCallState) -> bool:
        remaining = left()
        no_time = remaining is not None and remaining - (state.upcoming_sleep or 0) <= 0
        return tries(state) or no_time

    retrying = Retrying(
        retry=retry_if_result(again),
        wait=wait_chain(*(wait_fixed(w) for w in waits)) if waits else wait_fixed(0),
        stop=stop,
        sleep=sleep,
        retry_error_callback=lambda state: state.outcome.result() if state.outcome else None,
    )
    return retrying(lambda: attempt(left()))
