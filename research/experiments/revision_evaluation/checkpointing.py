# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Connect research trace boundaries to durable, incrementing attempt snapshots."""

import hashlib
import json
import time
from collections.abc import Callable
from copy import deepcopy
from dataclasses import asdict
from datetime import UTC, datetime

import httpx

from .contract import CheckEvent, Cost, ModelCall, Observation, OptionalNumber, TokenTotal
from .persistence import RunStore
from .reviser import TracedReviser
from .tracing import LogicalCallTrace, LogicalModelCallRecorder, active_logical_call
from .transport import CheckpointError, RecordingTransport


def _refresh_evidence_totals(value: Observation) -> None:
    """Keep checkpoint counts and known usage auditable; do not estimate absent usage.

    Cumulative run aggregation, pricing estimates and latency accounting belong
    to the telemetry layer. These totals cover only this checkpoint's evidence.
    """
    calls = value.model_calls
    attempts = [attempt for call in calls for attempt in call.http_attempts]
    totals = value.telemetry
    totals.logical_calls = len(calls)
    totals.reasks = sum(call.purpose == "reask" for call in calls)
    totals.http_attempts = len(attempts)
    totals.http_429_responses = sum(attempt.status_code == 429 for attempt in attempts)
    totals.http_429_retries = sum(
        attempt.status_code == 429 for call in calls for attempt in call.http_attempts[:-1]
    )
    durations = [attempt.provider_round_trip_s for attempt in attempts]
    timed = bool(durations) and all(duration is not None for duration in durations)
    totals.provider_round_trip_s = OptionalNumber(
        applicability="value" if timed else "unavailable" if attempts else "not_applicable",
        value=sum(durations) if timed else None,
    )
    for name in type(totals.tokens).model_fields:
        entries = [getattr(attempt.usage, name) if attempt.usage else None for attempt in attempts]
        subtotal = sum(entry for entry in entries if entry is not None)
        complete = bool(entries) and all(entry is not None for entry in entries)
        setattr(
            totals.tokens,
            name,
            TokenTotal(
                applicability="value"
                if complete
                else "unavailable"
                if entries
                else "not_applicable",
                value=subtotal if complete else None,
                confirmed_subtotal=subtotal,
            ),
        )
    costs = [attempt.cost_usd for attempt in attempts]
    measured = bool(costs) and all(cost.provenance == "measured" for cost in costs)
    subtotal = sum(cost.confirmed_subtotal for cost in costs)
    totals.cost_usd = Cost(
        applicability="value" if measured else "unavailable" if costs else "not_applicable",
        value=subtotal if measured else None,
        confirmed_subtotal=subtotal,
        provenance="measured" if measured else "missing" if costs else "not_applicable",
        price_inputs=None,
    )


class AttemptCheckpointer:
    """Own one fresh attempt; publish copies only after successful durable writes.

    The caller supplies immutable input and explicit terminal outcome/source;
    classification and compatible run reopening are intentionally separate layers.
    A new execution-attempt identity is required after interruption, never reuse.
    Use policy_time for both DishLLM and Reviser to exclude all checkpoint I/O.
    """

    def __init__(
        self, store: RunStore, initial: Observation, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        value = Observation.model_validate(initial.model_dump(by_alias=True))
        if (
            value.execution.state != "running"
            or value.execution.checkpoint_stage != "attempt_created"
            or value.execution.checkpoint_revision != 1
            or value.model_calls
            or value.checks
            or value.deterministic_evaluation.answers
            or value.deterministic_evaluation.deleted_ingredient_explanation.denominator
            or value.execution.finished_at is not None
            or value.execution.final_service_response is not None
            or value.execution.sanitized_error is not None
        ):
            raise ValueError("checkpointer requires a fresh running attempt")
        self.store, self._clock = store, clock
        self.checkpoint_persistence_s = 0.0
        _refresh_evidence_totals(value)
        self.observation = value
        self.reference = self._publish(value)

    def policy_time(self) -> float:
        """Exclude every completed persistence interval from production policy time."""
        return self._clock() - self.checkpoint_persistence_s

    def _publish(self, value: Observation) -> str:
        """Fail closed with a safe exception, without promoting an unwritten snapshot."""
        started = self._clock()
        try:
            return self.store.write_observation(value)
        except Exception:  # noqa: BLE001 - persistence errors must escape model error handling
            raise CheckpointError("checkpoint persistence failed") from None
        finally:
            self.checkpoint_persistence_s += self._clock() - started

    def _save(self, stage: str, *, call=None, checks=None, terminal=None) -> None:
        """Advance one revision on an isolated copy, preserving prior attempt evidence."""
        if self.observation.execution.state != "running":
            raise ValueError("attempt is no longer running")
        value = self.observation.model_copy(deep=True)
        value.execution.checkpoint_revision += 1
        value.execution.checkpoint_stage = stage
        if call is not None:
            request = asdict(call.request)
            request.pop("max_tokens")
            request["sha256"] = hashlib.sha256(
                json.dumps(asdict(call.request), ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            recorded = ModelCall(
                index=call.index,
                purpose=call.purpose,
                request=request,
                http_attempts=deepcopy(call.http_attempts),
                parsing=asdict(call.parsing),
                decoded_answer=deepcopy(call.decoded_answer),
            )
            if call.index == len(value.model_calls) + 1:
                value.model_calls.append(recorded)
            elif 1 <= call.index <= len(value.model_calls):
                value.model_calls[call.index - 1] = recorded
            else:
                raise ValueError("logical call index must be contiguous")
        if checks is not None:
            value.checks = deepcopy(checks)
        if terminal is not None:
            value.execution = type(value.execution).model_validate(
                {
                    **value.execution.model_dump(),
                    **terminal,
                }
            )
        _refresh_evidence_totals(value)
        checked = Observation.model_validate(value.model_dump(by_alias=True))
        self._publish(checked)
        self.observation = checked

    def record_http(self, call: LogicalCallTrace) -> None:
        """Persist prepared identity or completed HTTP evidence before control returns."""
        stage = (
            "request_prepared"
            if call.http_attempts[-1].state == "request_prepared"
            else "response_received"
        )
        self._save(stage, call=call)

    def record_parsing(self, call: LogicalCallTrace) -> None:
        """Persist parsing separately from HTTP receipt and later production checks."""
        self._save("json_parsed", call=call)

    def record_checks(self, checks: list[CheckEvent]) -> None:
        """Save check decisions before production can issue its conditional re-ask."""
        self._save("check_completed", checks=checks)

    def finish(self, *, outcome: str, source: str, response=None, error: str | None = None) -> None:
        """Save an explicitly classified terminal result before another repetition starts.

        Error text must already be sanitized by the calling classification layer.
        Interruption does not call this method: the last running checkpoint stays
        incomplete and a future resume must allocate a different attempt number.
        """
        self._save(
            "terminal",
            terminal={
                "state": "completed",
                "finished_at": datetime.now(UTC).isoformat(),
                "terminal_outcome": outcome,
                "outcome_source": source,
                "final_service_response": response.model_dump() if response is not None else None,
                "sanitized_error": error,
            },
        )


class CheckpointTransport(RecordingTransport):
    """Add the parsing boundary after the existing HTTP-before/after checkpoints."""

    def __init__(
        self, transport: httpx.BaseTransport, *, checkpointer: AttemptCheckpointer
    ) -> None:
        self.checkpointer = checkpointer
        super().__init__(transport, checkpoint=checkpointer.record_http, clock=checkpointer._clock)

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Save received usage first, then parse evidence before returning to DishLLM."""
        response = super().handle_request(request)
        try:
            call = active_logical_call()
            if call.parsing.attempted:
                self.checkpointer.record_parsing(call)
        except BaseException:
            response.close()
            raise
        return response


class CheckpointModelCallRecorder(LogicalModelCallRecorder):
    """Persist production-decoded answers before any subsequent check or re-ask."""

    def __init__(self, model, *, checkpointer: AttemptCheckpointer) -> None:
        super().__init__(model)
        self.checkpointer = checkpointer

    def complete(self, system, user, name, schema, max_tokens=None) -> dict:
        """Keep the original model result/error while saving newly decoded evidence."""
        # The HTTP hook already saved parsing even if production raises here.
        result = super().complete(system, user, name, schema, max_tokens)
        self.checkpointer.record_parsing(self.calls[-1])
        return result


class CheckpointReviser(TracedReviser):
    """Save delegated production check decisions without editing production modules."""

    def __init__(self, *args, checkpointer: AttemptCheckpointer, **kwargs) -> None:
        super().__init__(*args, clock=checkpointer.policy_time, **kwargs)
        self.checkpointer = checkpointer

    def _judge(self, *args, **kwargs):
        """Return unchanged production objects after the check outcome is durable."""
        result = super()._judge(*args, **kwargs)
        self.checkpointer.record_checks(self.checks)
        return result
