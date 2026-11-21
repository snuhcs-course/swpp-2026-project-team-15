# AI-generated with Codex (GPT-5.6 Sol), 2026-11-21; reviewed by Soohyun An
"""Offline tests for research-only Revision tracing adapters."""

import pytest
from experiments.revision_evaluation.tracing import (
    LogicalModelCallRecorder,
    record_safe_response_text,
)

from app.dishes.errors import DishLLMError


class FakeModel:
    """Return or raise scripted outcomes while optionally publishing raw assistant text."""

    def __init__(self, outcomes: list[tuple[str | None, object]]) -> None:
        self.outcomes = iter(outcomes)

    def complete(self, *args, **kwargs) -> dict:
        raw, outcome = next(self.outcomes)
        if raw is not None:
            record_safe_response_text(raw)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def call(recorder: LogicalModelCallRecorder, user: str = "user") -> dict:
    """Invoke the protocol with a compact deterministic request."""

    return recorder.complete("system", user, "dish_revise", {"type": "object"})


def test_records_one_logical_call_without_changing_the_returned_answer():
    answer = {"can_revise": True}
    recorder = LogicalModelCallRecorder(FakeModel([('{"can_revise": true}', answer)]))

    returned = call(recorder)

    assert returned is answer
    assert len(recorder.calls) == 1
    recorded = recorder.calls[0]
    assert (recorded.index, recorded.purpose) == (1, "initial")
    assert recorded.request.user == "user"
    assert recorded.safe_response_text == '{"can_revise": true}'
    assert recorded.parsing.attempted is True and recorded.parsing.succeeded is True
    assert recorded.decoded_answer is answer
    assert recorded.sanitized_error is None


def test_records_ordered_initial_and_reask_calls():
    recorder = LogicalModelCallRecorder(
        FakeModel([("{}", {"n": 1}), ("{}", {"n": 2})])
    )

    call(recorder, "initial")
    call(recorder, "reask")

    assert [(item.index, item.purpose) for item in recorder.calls] == [
        (1, "initial"),
        (2, "reask"),
    ]
    assert [item.request.user for item in recorder.calls] == ["initial", "reask"]


def test_malformed_json_is_retained_when_the_wrapped_model_rejects_it():
    error = DishLLMError("The model returned an invalid answer")
    recorder = LogicalModelCallRecorder(FakeModel([("{", error)]))

    with pytest.raises(DishLLMError) as caught:
        call(recorder)

    assert caught.value is error
    recorded = recorder.calls[0]
    assert recorded.safe_response_text == "{"
    assert recorded.parsing.attempted is True
    assert recorded.parsing.succeeded is False
    assert recorded.parsing.error == "invalid JSON"
    assert recorded.decoded_answer is None
    assert recorded.sanitized_error == "The model returned an invalid answer"


@pytest.mark.parametrize(
    "message",
    [
        "The model service is not configured",
        "The model service is temporarily unavailable",
        "The model service rejected the request",
        "The model service could not be reached",
        "The model returned an incomplete answer",
        "The model returned an invalid answer",
    ],
)
def test_known_production_error_message_is_preserved(message):
    error = DishLLMError(message)
    recorder = LogicalModelCallRecorder(FakeModel([(None, error)]))

    with pytest.raises(DishLLMError) as caught:
        call(recorder)

    assert caught.value is error
    assert recorder.calls[0].sanitized_error == message


@pytest.mark.parametrize("error_type", [RuntimeError, DishLLMError])
@pytest.mark.parametrize(
    "message",
    [
        "Authorization: Bearer secret-provider-body",
        "The model returned an invalid answer: secret-provider-body",
        "",
    ],
)
def test_unknown_failure_is_sanitized_without_changing_the_exception(error_type, message):
    error = error_type(message)
    recorder = LogicalModelCallRecorder(FakeModel([(None, error)]))

    with pytest.raises(error_type) as caught:
        call(recorder)

    assert caught.value is error
    recorded = recorder.calls[0]
    assert recorded.parsing.attempted is False
    assert recorded.parsing.succeeded is None
    assert recorded.sanitized_error == "model call failed"
    assert "secret-provider-body" not in recorded.sanitized_error
