# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Prove persistence failures escape production handlers before further billing."""

import json
from copy import deepcopy

import httpx
import pytest
from experiments.revision_evaluation import persistence
from experiments.revision_evaluation.checkpointing import (
    AttemptCheckpointer,
    CheckpointModelCallRecorder,
    CheckpointReviser,
    CheckpointTransport,
)
from experiments.revision_evaluation.contract import Observation
from experiments.revision_evaluation.persistence import RunStore
from experiments.revision_evaluation.transport import CheckpointError

from app.dishes.catalog import Catalog
from app.dishes.errors import DishLLMError
from app.dishes.llm import DishLLM
from app.dishes.recipes import RecipeStore
from app.dishes.schemas import SourceRecipe
from tests.dishes.test_dishes import STAPLES
from tests.dishes.test_revision import GOOD, RECIPE
from tests.experiments.revision_evaluation.test_checkpointing import initial_observation

# Each row identifies a real boundary in one 429/retry/failed-check/re-ask path.
# Counts are actual sends, not the number of prepared identities left in memory.
FAILURE_BOUNDARIES = [
    ("attempt_created", 1, 0),
    ("request_prepared", 1, 0),
    ("response_received", 1, 1),
    ("request_prepared", 2, 1),
    ("response_received", 2, 2),
    ("json_parsed", 1, 2),
    ("json_parsed", 2, 2),
    ("check_completed", 1, 2),
    ("request_prepared", 3, 2),
    ("response_received", 3, 3),
    ("json_parsed", 3, 3),
    ("json_parsed", 4, 3),
    ("check_completed", 2, 3),
    ("terminal", 1, 3),
]


def execute_plan_with_write_failure(
    tmp_path, monkeypatch, *, boundary, occurrence, operation, error_type=OSError
):
    """Exercise real atomic writes and model handlers in a two-repetition mock plan.

    This small caller catches only per-attempt model errors, as future Runner
    orchestration must do. A checkpoint failure must escape the entire loop,
    rather than being classified as an API error that permits another repetition.
    """
    store = RunStore(tmp_path, "checkpoint-run")
    write = store.write_observation
    snapshots, sends, started, controllers = [], [], [], []
    seen = [0]

    def fail(*args, **kwargs):
        raise error_type("Authorization: Bearer private-storage-detail")

    def save(value):
        if value.execution.checkpoint_stage == boundary:
            seen[0] += 1
        if value.execution.checkpoint_stage == boundary and seen[0] == occurrence:
            # Patch only the target write: earlier durable evidence is real.
            with monkeypatch.context() as scoped:
                scoped.setattr(persistence.os, operation, fail)
                return write(value)
        reference = write(value)
        snapshots.append((reference, (store.root / reference).read_bytes()))
        return reference

    store.write_observation = save

    def run_plan():
        for repetition in (1, 2):
            started.append(repetition)
            repetition_sends = []

            def handle(request, repetition=repetition, repetition_sends=repetition_sends):
                durable = Observation.model_validate_json(snapshots[-1][1])
                assert durable.execution.checkpoint_stage == "request_prepared"
                sends.append(repetition)
                repetition_sends.append(request)
                if len(repetition_sends) == 1:
                    return httpx.Response(429, json={"error": "private-provider-detail"})
                answer = {**GOOD, "changes": []} if len(repetition_sends) == 2 else GOOD
                return httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "finish_reason": "stop",
                                "message": {"content": json.dumps(answer, ensure_ascii=False)},
                            }
                        ],
                        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "cost": 0.01},
                    },
                )

            catalog = Catalog.load(staples=STAPLES)
            initial = initial_observation(catalog)
            initial.repetition = repetition
            checkpointer = AttemptCheckpointer(store, initial)
            controllers.append(checkpointer)
            transport = CheckpointTransport(httpx.MockTransport(handle), checkpointer=checkpointer)
            model = CheckpointModelCallRecorder(
                DishLLM(
                    "test-key",
                    transport=transport,
                    retry_waits=(0,),
                    clock=checkpointer.policy_time,
                ),
                checkpointer=checkpointer,
            )
            recipes = RecipeStore(
                {RECIPE["dish_id"]: SourceRecipe.model_validate(deepcopy(RECIPE))}
            )
            reviser = CheckpointReviser(catalog, catalog, model, recipes, checkpointer=checkpointer)
            try:
                response = reviser.revise(RECIPE["dish_id"], ["밥", "김치"])
            except DishLLMError:
                # Deliberately continue model errors to detect an incorrect conversion
                # of storage exceptions by DishLLM or its transport error handling.
                continue
            checkpointer.finish(outcome="revised", source="model", response=response)

    return store, snapshots, sends, started, controllers, run_plan


@pytest.mark.parametrize("operation", ["fsync", "replace"])
@pytest.mark.parametrize("boundary,occurrence,expected_sends", FAILURE_BOUNDARIES)
def test_atomic_write_failure_stops_retry_reask_and_next_repetition(
    tmp_path, monkeypatch, boundary, occurrence, expected_sends, operation
):
    store, snapshots, sends, started, controllers, run = execute_plan_with_write_failure(
        tmp_path, monkeypatch, boundary=boundary, occurrence=occurrence, operation=operation
    )
    with pytest.raises(CheckpointError, match="^checkpoint persistence failed$"):
        run()
    assert len(sends) == expected_sends
    assert started == [1]
    assert list(store.root.rglob("*.tmp")) == []
    if not snapshots:
        assert list(store.root.rglob("attempt-*.json")) == []
        return
    reference, before = snapshots[-1]
    assert (store.root / reference).read_bytes() == before
    saved = Observation.model_validate_json(before)
    assert saved.execution.state == "running"
    assert saved.execution.terminal_outcome is None
    assert controllers[0].observation == saved
    if boundary == "request_prepared":
        # Failed intent writes consume no durable identity/budget unit.
        assert saved.telemetry.http_attempts == expected_sends
    elif boundary == "response_received":
        # A response that could not be saved must remain uncertain on disk.
        http = saved.model_calls[-1].http_attempts[-1]
        assert http.state == "request_prepared" and http.delivery == "unknown"
        assert http.usage is None and http.cost_usd.value is None
    elif expected_sends >= 2:
        assert saved.model_calls[0].http_attempts[1].cost_usd.value == 0.01
    assert "private-storage-detail" not in before.decode("utf-8")
    assert "private-provider-detail" not in before.decode("utf-8")


@pytest.mark.parametrize("error_type", [ValueError, httpx.ConnectError, httpx.ReadTimeout])
@pytest.mark.parametrize(
    "boundary,occurrence,expected_sends",
    [
        ("request_prepared", 1, 0),
        ("response_received", 1, 1),
        ("json_parsed", 1, 2),
        ("check_completed", 1, 2),
    ],
)
def test_storage_exception_types_cannot_become_recoverable_model_errors(
    tmp_path, monkeypatch, error_type, boundary, occurrence, expected_sends
):
    _, _, sends, started, _, run = execute_plan_with_write_failure(
        tmp_path,
        monkeypatch,
        boundary=boundary,
        occurrence=occurrence,
        operation="replace",
        error_type=error_type,
    )
    with pytest.raises(CheckpointError, match="^checkpoint persistence failed$"):
        run()
    assert len(sends) == expected_sends and started == [1]


def test_control_plan_reaches_both_repetitions_without_storage_failure(tmp_path, monkeypatch):
    store, _, sends, started, _, run = execute_plan_with_write_failure(
        tmp_path, monkeypatch, boundary="never", occurrence=1, operation="replace"
    )
    run()
    assert started == [1, 2] and sends == [1, 1, 1, 2, 2, 2]
    assert len(list(store.root.rglob("attempt-*.json"))) == 2
