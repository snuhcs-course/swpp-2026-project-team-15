# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Classify actual production completion separately from deterministic findings."""

from dataclasses import dataclass
from typing import Literal

from app.dishes.errors import MODEL_NOT_CONFIGURED, DishLLMError
from app.dishes.schemas import ReviseResponse

from .checkpointing import AttemptCheckpointer
from .contract import Observation
from .tracing import SAFE_MODEL_ERROR_MESSAGES


@dataclass(frozen=True)
class TerminalResult:
    """A completed production outcome and its stage, with safe model failure text."""

    outcome: Literal[
        "unchanged", "revised", "refused", "check_failed", "response_error", "api_error"
    ]
    source: Literal["no_change", "prescreen", "model", "production_check", "response", "transport"]
    error: str | None = None


def classify_terminal(
    observation: Observation,
    *,
    response: ReviseResponse | None = None,
    error: BaseException | None = None,
) -> TerminalResult | None:
    """Classify an explicit service response/model error without changing evidence.

    No return value/error means there is no observed completion. Operational,
    configuration and interruption exceptions propagate unchanged; they are not
    completed API failures. Offline structure/reference scores never decide the
    production outcome, including when production salvages a truncated answer.
    """
    if response is not None and error is not None:
        raise ValueError("completion cannot contain both a response and an error")
    if error is not None:
        if not isinstance(error, DishLLMError) or str(error) == MODEL_NOT_CONFIGURED:
            raise error
        if observation.execution.state == "interrupted":
            return None
        # Only the final logical call owns the failure. A successful first call
        # must not turn a later failed re-ask into a response error.
        call = observation.model_calls[-1] if observation.model_calls else None
        http = call.http_attempts[-1] if call and call.http_attempts else None
        if http is not None and http.state == "request_prepared":
            return None  # Unknown delivery is not evidence of completed failure.
        message = str(error)
        safe_error = message if message in SAFE_MODEL_ERROR_MESSAGES else "model call failed"
        if http is not None and http.state == "response_received" and http.status_code == 200:
            return TerminalResult("response_error", "response", safe_error)
        return TerminalResult("api_error", "transport", safe_error)
    if response is None or observation.execution.state == "interrupted":
        return None
    if response.status == "failed":
        return TerminalResult("check_failed", "production_check")
    if response.status == "refused":
        if not observation.model_calls:
            return TerminalResult("refused", "prescreen")
        check_owned = bool(observation.checks) and observation.checks[-1].result == "refusal_needed"
        return TerminalResult("refused", "production_check" if check_owned else "model")
    if not observation.model_calls and "unavailable" not in observation.input.availability:
        return TerminalResult("unchanged", "no_change")
    return TerminalResult("revised", "model")


def persist_terminal(
    checkpointer: AttemptCheckpointer,
    *,
    response: ReviseResponse | None = None,
    error: BaseException | None = None,
) -> TerminalResult | None:
    """Publish a classified terminal checkpoint, or leave incomplete evidence untouched.

    The caller supplies the actual completed response or raised model exception;
    this function does not execute Revision, catch operational failures or resume.
    """
    result = classify_terminal(checkpointer.observation, response=response, error=error)
    if result is not None:
        checkpointer.finish(
            outcome=result.outcome,
            source=result.source,
            response=response,
            error=result.error,
        )
    return result
