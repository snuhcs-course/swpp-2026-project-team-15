# AI-assisted with Codex, 2026-11-21; Reviewed by Soohyun An
"""Offline integration tests against the production DishLLM and retry behavior."""

from dataclasses import asdict

import httpx
import pytest
from experiments.revision_evaluation.contract import HttpAttempt
from experiments.revision_evaluation.tracing import LogicalModelCallRecorder
from experiments.revision_evaluation.transport import CheckpointError, RecordingTransport

from app.dishes.errors import DishLLMError
from app.dishes.llm import DishLLM


def invoke(model):
    """Exercise the production model protocol without a live network transport."""
    return model.complete("system", "user", "dish_revise", {"type": "object"})


def response_body(content='{"can_revise": true}'):
    """Include allowlisted measurements and extra fields that must be discarded."""
    return {
        "choices": [{"finish_reason": "stop", "message": {"content": content}}],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "completion_tokens_details": {"reasoning_tokens": 3},
            "prompt_tokens_details": {"cached_tokens": 4},
            "cost": 0.001,
            "private": "provider-secret",
        },
        "private": "provider-secret",
    }


def test_429_retry_is_checkpointed_before_each_send_and_correlated_with_one_call():
    checkpoints, sends = [], []

    def handle(request):
        # Durable intent precedes every send, including a retry inside one call.
        prepared = checkpoints[-1].http_attempts[-1]
        assert prepared.state == "request_prepared"
        assert prepared.index == len(sends) + 1
        assert prepared.usage is None and prepared.cost_usd.value is None
        sends.append(request.content)
        if len(sends) == 1:
            return httpx.Response(429, json={"error": "provider-secret"})
        return httpx.Response(200, json=response_body(), headers={"secret": "header-secret"})

    transport = RecordingTransport(httpx.MockTransport(handle), checkpoint=checkpoints.append)
    model = LogicalModelCallRecorder(DishLLM("api-secret", transport=transport, retry_waits=(0,)))

    assert invoke(model) == {"can_revise": True}

    assert len(model.calls) == 1 and len(sends) == 2 and sends[0] == sends[1]
    assert [snapshot.http_attempts[-1].state for snapshot in checkpoints] == [
        "request_prepared",
        "response_received",
        "request_prepared",
        "response_received",
    ]
    attempts = model.calls[0].http_attempts
    assert [attempt.status_code for attempt in attempts] == [429, 200]
    assert attempts[0].safe_response_text is None
    assert attempts[1].usage.model_dump() == {
        "input_tokens": 10,
        "output_tokens": 20,
        "reasoning_tokens": 3,
        "cached_tokens": 4,
    }
    assert attempts[1].cost_usd.provenance == "measured"
    assert attempts[1].cost_usd.value == 0.001
    assert attempts[1].finish_reason == "stop"
    assert model.calls[0].parsing.succeeded is True
    assert "secret" not in repr([asdict(snapshot) for snapshot in checkpoints])
    for snapshot in checkpoints:
        for attempt in snapshot.http_attempts:
            HttpAttempt.model_validate(attempt.model_dump())


@pytest.mark.parametrize("fail_at,expected_sends", [(1, 0), (2, 1)])
@pytest.mark.parametrize("error_type", [ValueError, OSError, httpx.ReadError])
def test_checkpoint_failure_stops_before_send_or_retry(fail_at, expected_sends, error_type):
    sends, checkpoints = [], []

    def save(call):
        checkpoints.append(call)
        if len(checkpoints) == fail_at:
            raise error_type("storage-secret")

    def handle(request):
        sends.append(request)
        return httpx.Response(429, json={"error": "provider-secret"})

    transport = RecordingTransport(httpx.MockTransport(handle), checkpoint=save)
    model = LogicalModelCallRecorder(DishLLM("key", transport=transport, retry_waits=(0,)))
    with pytest.raises(CheckpointError, match="^checkpoint persistence failed$"):
        invoke(model)
    assert len(sends) == expected_sends


def test_transport_failure_is_preserved_without_persisting_exception_text():
    checkpoints = []

    def handle(request):
        raise httpx.ConnectError("Authorization: Bearer transport-secret")

    transport = RecordingTransport(httpx.MockTransport(handle), checkpoint=checkpoints.append)
    model = LogicalModelCallRecorder(DishLLM("key", transport=transport))
    with pytest.raises(DishLLMError, match="could not be reached"):
        invoke(model)
    attempt = checkpoints[-1].http_attempts[-1]
    assert attempt.state == "transport_error"
    assert attempt.status_code is None and attempt.usage is None
    assert attempt.cost_usd.provenance == "missing"
    assert "transport-secret" not in repr([asdict(item) for item in checkpoints])


def test_malformed_assistant_json_remains_visible_after_production_rejects_it():
    checkpoints = []
    transport = RecordingTransport(
        httpx.MockTransport(lambda request: httpx.Response(200, json=response_body("{"))),
        checkpoint=checkpoints.append,
    )
    model = LogicalModelCallRecorder(DishLLM("key", transport=transport))
    with pytest.raises(DishLLMError, match="invalid answer"):
        invoke(model)
    assert model.calls[0].safe_response_text == "{"
    assert model.calls[0].parsing.succeeded is False
    assert checkpoints[-1].http_attempts[-1].safe_response_text == "{"


def test_provider_time_excludes_checkpoint_duration():
    now = [0.0]

    def save(call):
        now[0] += 2

    def handle(request):
        now[0] += 0.25
        return httpx.Response(200, json=response_body())

    transport = RecordingTransport(
        httpx.MockTransport(handle),
        checkpoint=save,
        clock=lambda: now[0],
    )
    model = LogicalModelCallRecorder(DishLLM("key", transport=transport))
    invoke(model)
    assert model.calls[0].http_attempts[0].provider_round_trip_s == 0.25
    assert transport.checkpoint_persistence_s == 4


def test_missing_logical_context_prevents_delegation():
    sends = []
    transport = RecordingTransport(
        httpx.MockTransport(lambda request: sends.append(request)),
        checkpoint=lambda call: None,
    )
    with httpx.Client(transport=transport) as client:
        with pytest.raises(RuntimeError, match="no logical model call"):
            client.post("https://example.invalid", json={"model": "test"})
    assert sends == []


def test_attempt_numbers_restart_for_each_logical_call():
    checkpoints = []
    transport = RecordingTransport(
        httpx.MockTransport(lambda request: httpx.Response(200, json=response_body())),
        checkpoint=checkpoints.append,
    )
    model = LogicalModelCallRecorder(DishLLM("key", transport=transport))
    assert invoke(model) == invoke(model) == {"can_revise": True}
    assert [call.purpose for call in model.calls] == ["initial", "reask"]
    assert [call.http_attempts[0].index for call in model.calls] == [1, 1]
    assert [call.index for call in checkpoints] == [1, 1, 2, 2]


@pytest.mark.parametrize("status", [400, 429, 500])
def test_error_bodies_do_not_enter_persisted_records(status):
    checkpoints = []
    transport = RecordingTransport(
        httpx.MockTransport(
            lambda request: httpx.Response(
                status,
                json=response_body('"provider-secret"'),
                headers={"Authorization": "Bearer header-secret"},
            )
        ),
        checkpoint=checkpoints.append,
    )
    model = LogicalModelCallRecorder(DishLLM("key", transport=transport, retry_waits=()))
    with pytest.raises(DishLLMError):
        invoke(model)
    attempt = model.calls[0].http_attempts[0]
    assert attempt.status_code == status
    assert attempt.safe_response_text is None and attempt.finish_reason is None
    assert attempt.usage is None and attempt.cost_usd.provenance == "missing"
    assert "secret" not in repr([asdict(item) for item in checkpoints])


def test_partial_or_invalid_usage_is_not_converted_to_zero():
    body = response_body()
    body["usage"] = {"prompt_tokens": 0, "completion_tokens": True, "cost": -1}
    transport = RecordingTransport(
        httpx.MockTransport(lambda request: httpx.Response(200, json=body)),
        checkpoint=lambda call: None,
    )
    model = LogicalModelCallRecorder(DishLLM("key", transport=transport))
    invoke(model)
    attempt = model.calls[0].http_attempts[0]
    assert attempt.usage.input_tokens == 0
    assert attempt.usage.output_tokens is None
    assert attempt.usage.reasoning_tokens is None
    assert attempt.usage.cached_tokens is None
    assert attempt.cost_usd.provenance == "missing"
