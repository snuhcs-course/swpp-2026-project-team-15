# AI-assisted with Codex, 2026-11-22; reviewed by Soohyun An
"""Restore research storage failures across SDK wrapping without changing model errors."""

import json
import socket
import traceback

import httpx
import openai
import pytest
from experiments.revision_evaluation import live, runner
from experiments.revision_evaluation.tracing import LogicalModelCallRecorder, active_logical_call
from experiments.revision_evaluation.transport import CheckpointError

from app.dishes.errors import DishLLMError
from tests.dishes.test_revision import GOOD
from tests.experiments.revision_evaluation.test_runner import answer, artifacts, setup
from tests.experiments.revision_evaluation.test_runner import no_network as no_network
from tests.experiments.revision_evaluation.test_tracing import FakeModel, call


@pytest.mark.parametrize("link", ["cause", "context", "both_with_cycle"])
def test_wrapped_checkpoint_error_is_restored_with_safe_text_and_context_cleanup(link):
    """Walk both exception links, including cycles, without publishing private causes."""
    storage = CheckpointError("private-storage-detail")
    connection = RuntimeError("private-provider-detail")
    error = DishLLMError("The model service could not be reached")
    if link == "cause":
        error.__cause__ = connection
        connection.__cause__ = storage
    elif link == "context":
        error.__context__ = connection
        connection.__context__ = storage
    else:
        error.__cause__ = connection
        connection.__cause__ = error
        error.__context__ = storage
    recorder = LogicalModelCallRecorder(FakeModel([(None, error)]))

    with pytest.raises(CheckpointError, match="^checkpoint persistence failed$") as caught:
        call(recorder)

    assert recorder.calls[0].sanitized_error == "model call failed"
    assert recorder.calls[0].decoded_answer is None
    assert "private-" not in "".join(traceback.format_exception(caught.value))
    with pytest.raises(RuntimeError, match="no logical model call is active"):
        active_logical_call()


@pytest.mark.parametrize("kind", ["connection", "cycle", "same_name", "direct_checkpoint"])
def test_other_errors_keep_the_original_exception(kind):
    """Do not infer persistence failure from class names, message text, or arbitrary cycles."""
    error = DishLLMError("The model service could not be reached")
    nested = RuntimeError("checkpoint persistence failed")
    if kind == "cycle":
        nested.__context__ = error
    elif kind == "same_name":
        nested = type("CheckpointError", (RuntimeError,), {})("checkpoint persistence failed")
    elif kind == "direct_checkpoint":
        error = CheckpointError("checkpoint persistence failed")
    error.__cause__ = nested
    recorder = LogicalModelCallRecorder(FakeModel([(None, error)]))

    with pytest.raises(type(error)) as caught:
        call(recorder)
    assert caught.value is error
    assert recorder.calls[0].sanitized_error == (
        "model call failed" if kind == "direct_checkpoint" else str(error)
    )


@pytest.mark.parametrize(
    "boundary", ["first_intent", "parsing", "retry_intent", "reask_intent", "response_write"]
)
def test_one_shot_checkpoint_failure_stops_real_sdk_runner(tmp_path, monkeypatch, boundary):
    """Fail only repetition two; later successful writes must not permit repetition three."""

    def forbidden(*args, **kwargs):
        raise AssertionError("real networking is forbidden")

    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    plan, metadata, kwargs = setup(repetitions=3)
    sends, failures, models, wrapped_errors = [], [], [], []
    original_write = runner._EvaluatedStore._write
    original_factory = live.DishLLM
    root = tmp_path / "runner-test"
    first = root / "observations/runner-case__r01/attempt-001.json"
    target = root / "observations/runner-case__r02/attempt-001.json"

    def make_model(*args, **kwargs):
        model = original_factory(*args, **kwargs)
        models.append(model)
        complete = model.complete

        def observe(*args, **kwargs):
            try:
                return complete(*args, **kwargs)
            except DishLLMError as error:
                wrapped_errors.append(error)
                raise

        monkeypatch.setattr(model, "complete", observe)
        return model

    def write(self, relative, value):
        stage = value.get("execution", {}).get("checkpoint_stage")
        calls = value.get("model_calls", [])
        current = calls[-1] if calls else None
        intent = stage == "request_prepared"
        match = value.get("repetition") == 2 and (
            (boundary == "first_intent" and intent and current["index"] == 1)
            or (boundary == "parsing" and stage == "json_parsed")
            or (boundary == "retry_intent" and intent and len(current["http_attempts"]) == 2)
            or (boundary == "reask_intent" and intent and current["index"] == 2)
            or (boundary == "response_write" and stage == "response_received")
        )
        if match and not failures:
            failures.append((len(sends), first.read_bytes(), target.read_bytes()))
            raise OSError("private-storage-detail")
        return original_write(self, relative, value)

    def handle(request):
        sends.append(request)
        if len(sends) == 2 and boundary == "retry_intent":
            return httpx.Response(429)
        if len(sends) == 2 and boundary == "reask_intent":
            return answer({**GOOD, "changes": []})
        return answer()

    monkeypatch.setattr(live, "DishLLM", make_model)
    monkeypatch.setattr(runner._EvaluatedStore, "_write", write)
    try:
        with pytest.raises(CheckpointError, match="^checkpoint persistence failed$"):
            runner.run_new(
                plan,
                metadata,
                parent=tmp_path,
                transport_factory=lambda: httpx.MockTransport(handle),
                **kwargs,
            )
    finally:
        for model in models:
            model._client.close()

    saved, summary, observations = artifacts(tmp_path)
    assert len(failures) == 1 and len(sends) == failures[0][0]
    assert len(sends) == (1 if boundary == "first_intent" else 2)
    assert first.read_bytes() == failures[0][1]
    assert target.read_bytes() == failures[0][2]
    assert saved.state == "interrupted" and not summary.complete
    assert [unit.state for unit in saved.plan] == ["completed", "incomplete", "not_started"]
    assert [item.execution.terminal_outcome for item in observations] == ["revised", None]
    assert observations[-1].execution.state == "running"
    assert len(wrapped_errors) == 1
    # This asserts actual SDK wrapping, rather than a fake DishLLMError test double.
    assert isinstance(wrapped_errors[0].__context__, openai.APIConnectionError)
    assert isinstance(wrapped_errors[0].__context__.__cause__, CheckpointError)
    previous = json.loads(failures[0][2])
    assert observations[-1].execution.checkpoint_stage == previous["execution"]["checkpoint_stage"]
