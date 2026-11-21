# AI-generated with Codex (GPT-5.6 Sol), 2026-11-21; reviewed by Soohyun An
"""Research-only tracing adapters for the production dish Revision path."""

from __future__ import annotations

import json
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Literal

from app.dishes.errors import MODEL_NOT_CONFIGURED, DishLLMError
from app.dishes.roles import ChatModel

# Match production's fixed messages exactly: an exception's type alone does not
# guarantee that a different ChatModel implementation supplied safe text.
SAFE_MODEL_ERROR_MESSAGES = frozenset(
    {
        MODEL_NOT_CONFIGURED,
        "The model service is temporarily unavailable",
        "The model service rejected the request",
        "The model service could not be reached",
        "The model returned an incomplete answer",
        "The model returned an invalid answer",
    }
)


@dataclass(frozen=True)
class RecordedRequest:
    """An immutable copy of one logical model request."""

    system: str
    user: str
    name: str
    schema: dict[str, Any]
    max_tokens: int | None


@dataclass
class ParsingTrace:
    """JSON parsing evidence captured independently from the production result."""

    attempted: bool = False
    succeeded: bool | None = None
    error: str | None = None


@dataclass
class LogicalCallTrace:
    """Evidence for one initial or check-triggered re-ask model call."""

    index: int
    purpose: Literal["initial", "reask"]
    request: RecordedRequest
    safe_response_text: str | None = None
    parsing: ParsingTrace = field(default_factory=ParsingTrace)
    decoded_answer: Any = None
    sanitized_error: str | None = None


_active_call: ContextVar[LogicalCallTrace | None] = ContextVar(
    "revision_evaluation_active_call", default=None
)


def record_safe_response_text(text: str) -> None:
    """Attach allowlisted assistant text and its JSON parse result to the active call.

    The HTTP recorder calls this hook after extracting assistant content. Keeping the
    hook here lets malformed JSON remain observable even when the production model
    raises instead of returning a decoded value.
    """

    call = _active_call.get()
    if call is None:
        raise RuntimeError("no logical model call is active")
    call.safe_response_text = text
    call.parsing.attempted = True
    try:
        json.loads(text)
    except (TypeError, ValueError):
        call.parsing.succeeded = False
        call.parsing.error = "invalid JSON"
    else:
        call.parsing.succeeded = True
        call.parsing.error = None


class LogicalModelCallRecorder:
    """Wrap a ChatModel without changing its returned value or raised exception."""

    def __init__(self, model: ChatModel) -> None:
        self._model = model
        self.calls: list[LogicalCallTrace] = []

    def complete(
        self,
        system: str,
        user: str,
        name: str,
        schema: dict,
        max_tokens: int | None = None,
    ) -> dict:
        """Delegate one call while recording request, parsing, answer, and safe failure data."""

        call = LogicalCallTrace(
            index=len(self.calls) + 1,
            purpose="initial" if not self.calls else "reask",
            request=RecordedRequest(
                system=system,
                user=user,
                name=name,
                schema=deepcopy(schema),
                max_tokens=max_tokens,
            ),
        )
        self.calls.append(call)
        token = _active_call.set(call)
        try:
            result = self._model.complete(system, user, name, schema, max_tokens)
        except Exception as error:
            message = str(error) if isinstance(error, DishLLMError) else None
            call.sanitized_error = (
                message if message in SAFE_MODEL_ERROR_MESSAGES else "model call failed"
            )
            raise
        else:
            call.decoded_answer = result
            return result
        finally:
            _active_call.reset(token)
