# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""HTTP recording around the production model's injectable synchronous transport."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable
from copy import deepcopy
from datetime import UTC, datetime

import httpx

from .contract import Cost, HttpAttempt, Usage
from .tracing import LogicalCallTrace, active_logical_call, record_safe_response_text


class CheckpointError(RuntimeError):
    """Stop execution when evidence cannot be saved before another billable action."""


def _missing_cost() -> Cost:
    """Represent unknown billing without claiming the attempt was free."""
    return Cost(
        applicability="unavailable",
        value=None,
        confirmed_subtotal=0,
        provenance="missing",
        price_inputs=None,
    )


def _token_count(value: object) -> int | None:
    """Reject malformed provider counters rather than coercing them into measurements."""
    return value if type(value) is int and value >= 0 else None


def _record_response(attempt: HttpAttempt, response: httpx.Response) -> None:
    """Copy only allowlisted successful-response metadata; never retain error bodies."""
    if response.status_code != 200:
        return
    try:
        body = response.json()
    except (ValueError, UnicodeError):
        return
    if not isinstance(body, dict):
        return
    choices = body.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices else None
    if isinstance(choice, dict):
        finish = choice.get("finish_reason")
        # Unknown provider strings might contain arbitrary error details.
        if finish in ("stop", "length", "content_filter", "tool_calls", "function_call"):
            attempt.finish_reason = finish
        message = choice.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            attempt.safe_response_text = message["content"]
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return
    completion = usage.get("completion_tokens_details")
    prompt = usage.get("prompt_tokens_details")
    attempt.usage = Usage(
        input_tokens=_token_count(usage.get("prompt_tokens")),
        output_tokens=_token_count(usage.get("completion_tokens")),
        reasoning_tokens=_token_count(completion.get("reasoning_tokens"))
        if isinstance(completion, dict)
        else None,
        cached_tokens=_token_count(prompt.get("cached_tokens"))
        if isinstance(prompt, dict)
        else None,
    )
    cost = usage.get("cost")
    if type(cost) in (int, float) and math.isfinite(cost) and cost >= 0:
        attempt.cost_usd = Cost(
            applicability="value",
            value=cost,
            confirmed_subtotal=cost,
            provenance="measured",
            price_inputs=None,
        )


class RecordingTransport(httpx.BaseTransport):
    """Record correlated HTTP attempts and require synchronous durable checkpoints.

    `checkpoint` receives an isolated call snapshot and must return only after it
    is durably saved, or raise. Atomic file persistence is supplied by the Runner.
    The injected clock measures provider and checkpoint durations independently.
    Pass `policy_time` to both DishLLM and Reviser to exclude checkpoint duration
    from retry, timeout, and re-ask decisions while retaining observed wall time.
    """

    def __init__(
        self,
        transport: httpx.BaseTransport,
        *,
        checkpoint: Callable[[LogicalCallTrace], None],
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transport = transport
        self._checkpoint = checkpoint
        self._clock = clock
        self.checkpoint_persistence_s = 0.0

    def policy_time(self) -> float:
        """Return a shared policy clock with completed checkpoint intervals removed."""
        return self._clock() - self.checkpoint_persistence_s

    def _save(self, call: LogicalCallTrace) -> None:
        """Make checkpoint failures escape DishLLM's response/transport error handlers."""
        started = self._clock()
        try:
            self._checkpoint(deepcopy(call))
        except Exception:  # noqa: BLE001 - every persistence failure must stop billing
            # A storage ValueError or httpx error must not become a completed model
            # failure: that would allow the Runner to start another paid request.
            raise CheckpointError("checkpoint persistence failed") from None
        finally:
            self.checkpoint_persistence_s += self._clock() - started

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Checkpoint intent, delegate unchanged, then checkpoint allowlisted evidence."""
        call = active_logical_call()
        payload = json.loads(request.content)
        attempt = HttpAttempt(
            index=len(call.http_attempts) + 1,
            state="request_prepared",
            prepared_at=datetime.now(UTC).isoformat(),
            request_sha256=hashlib.sha256(request.content).hexdigest(),
            model=payload["model"],
            counts_against_budget=True,
            delivery="unknown",
            status_code=None,
            provider_round_trip_s=None,
            finish_reason=None,
            safe_response_text=None,
            usage=None,
            cost_usd=_missing_cost(),
        )
        call.http_attempts.append(attempt)
        self._save(call)
        started = self._clock()
        response = None
        try:
            response = self._transport.handle_request(request)
            # Include body delivery in provider time. Reading caches bytes on the
            # same response so production receives its original JSON unchanged.
            response.read()
        except httpx.TransportError:
            attempt.state = "transport_error"
            attempt.delivery = "failed"
            attempt.provider_round_trip_s = self._clock() - started
            if response is not None:
                response.close()
            self._save(call)
            raise
        except BaseException:
            if response is not None:
                response.close()
            raise
        attempt.provider_round_trip_s = self._clock() - started
        attempt.state = "response_received"
        attempt.delivery = "confirmed"
        attempt.status_code = response.status_code
        try:
            _record_response(attempt, response)
            # Persist received cost and text before production may retry or parse.
            self._save(call)
            if attempt.safe_response_text is not None:
                record_safe_response_text(attempt.safe_response_text)
        except BaseException:
            response.close()
            raise
        return response

    def close(self) -> None:
        """Delegate transport cleanup through HTTPX's normal ownership boundary."""
        self._transport.close()
