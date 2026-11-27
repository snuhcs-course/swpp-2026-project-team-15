# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Offline filesystem tests of attempt checkpoints at actual Revision boundaries."""

import json
from copy import deepcopy

import httpx
import pytest
from experiments.revision_evaluation.checkpointing import (
    AttemptCheckpointer,
    CheckpointModelCallRecorder,
    CheckpointReviser,
    CheckpointTransport,
)
from experiments.revision_evaluation.contract import Observation, SourceRecipeSnapshot
from experiments.revision_evaluation.generate_contract import fixture_observations
from experiments.revision_evaluation.persistence import RunStore
from experiments.revision_evaluation.transport import CheckpointError

from app.dishes.catalog import Catalog
from app.dishes.errors import DishLLMError
from app.dishes.llm import DishLLM
from app.dishes.recipes import RecipeStore
from app.dishes.schemas import SourceRecipe
from tests.dishes.test_dishes import STAPLES
from tests.dishes.test_revision import GOOD, RECIPE


class Halt(BaseException):
    """Simulate process interruption without converting it to a model failure."""


def initial_observation(catalog, *, execution_attempt=1):
    """Supply an empty, contract-valid attempt with immutable production input."""
    value = fixture_observations()["unchanged__r01/attempt-001.json"]
    value.update(
        run_id="checkpoint-run", case_id="checkpoint-case", execution_attempt=execution_attempt
    )
    value["input"].update(
        dish_id=RECIPE["dish_id"],
        dish_name=catalog.get(RECIPE["dish_id"]).name,
        supplied_ingredients=["밥", "김치"],
        effective_assumed_staples=list(STAPLES),
        original_recipe={key: deepcopy(RECIPE[key]) for key in SourceRecipeSnapshot.model_fields},
        availability=[
            catalog.status(row["name"], catalog.owned(["밥", "김치"]))
            for row in RECIPE["ingredients"]
        ],
    )
    value["execution"].update(
        state="running",
        checkpoint_stage="attempt_created",
        checkpoint_revision=1,
        finished_at=None,
        terminal_outcome=None,
        outcome_source=None,
        final_service_response=None,
    )
    for name in (
        "revision_s",
        "observed_wall_s",
        "checkpoint_persistence_s",
        "non_http_remainder_s",
    ):
        value["telemetry"][name] = {"applicability": "unavailable", "value": None}
    return Observation.model_validate(value)


def run_execution(tmp_path, *, interrupt=None, occurrence=1, delay=0, malformed=False):
    """Run real production retry/re-ask behavior using only a mock provider."""
    now, sends, snapshots = [0.0], [], []
    store = RunStore(tmp_path, "checkpoint-run")
    write = store.write_observation

    def save(value):
        reference = write(value)
        snapshots.append(
            Observation.model_validate_json((store.root / reference).read_text(encoding="utf-8"))
        )
        now[0] += delay
        if (
            value.execution.checkpoint_stage == interrupt
            and sum(item.execution.checkpoint_stage == interrupt for item in snapshots)
            == occurrence
        ):
            raise Halt()
        return reference

    store.write_observation = save

    def handle(request):
        # The exact request identity must already be durable when sending begins.
        latest = snapshots[-1]
        assert latest.execution.checkpoint_stage == "request_prepared"
        assert latest.model_calls[-1].http_attempts[-1].delivery == "unknown"
        sends.append(deepcopy(latest))
        now[0] += 0.25
        if interrupt == "during_send":
            raise Halt()
        if len(sends) == 1:
            return httpx.Response(429, json={"error": "private provider body"})
        answer = {**GOOD, "changes": []} if len(sends) == 2 else GOOD
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": "{bad"
                            if malformed
                            else json.dumps(answer, ensure_ascii=False)
                        },
                    }
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "cost": 0.01},
            },
        )

    catalog = Catalog.load(staples=STAPLES)
    controller, result = None, None
    try:
        controller = AttemptCheckpointer(store, initial_observation(catalog), clock=lambda: now[0])
        transport = CheckpointTransport(httpx.MockTransport(handle), checkpointer=controller)
        model = CheckpointModelCallRecorder(
            DishLLM(
                "test-key", transport=transport, retry_waits=(0,), clock=controller.policy_time
            ),
            checkpointer=controller,
        )
        recipes = RecipeStore({RECIPE["dish_id"]: SourceRecipe.model_validate(deepcopy(RECIPE))})
        reviser = CheckpointReviser(catalog, catalog, model, recipes, checkpointer=controller)
        result = reviser.revise(RECIPE["dish_id"], ["밥", "김치"])
        controller.finish(outcome="revised", source="model", response=result)
    except (Halt, DishLLMError):
        pass
    return store, snapshots, sends, controller, result


def test_every_boundary_is_incremented_and_usage_is_durable_before_retry_or_reask(tmp_path):
    store, snapshots, sends, controller, result = run_execution(tmp_path)
    stages = [item.execution.checkpoint_stage for item in snapshots]
    assert stages == [
        "attempt_created",
        "request_prepared",
        "response_received",
        "request_prepared",
        "response_received",
        "json_parsed",
        "json_parsed",
        "check_completed",
        "request_prepared",
        "response_received",
        "json_parsed",
        "json_parsed",
        "check_completed",
        "terminal",
    ]
    assert [item.execution.checkpoint_revision for item in snapshots] == list(range(1, 15))
    assert len(sends) == 3 and result.status == "revised"
    assert snapshots[4].model_calls[0].parsing.attempted is False
    assert snapshots[5].model_calls[0].parsing.succeeded is True
    assert snapshots[5].model_calls[0].decoded_answer is None
    assert snapshots[6].model_calls[0].decoded_answer is not None
    # Initial usage/cost and failed check survive preparation of the re-ask.
    assert sends[2].model_calls[0].http_attempts[1].cost_usd.value == 0.01
    assert sends[2].model_calls[0].http_attempts[1].usage.input_tokens == 10
    assert sends[2].checks[0].code == "unexplained_change"
    assert snapshots[-1].telemetry.tokens.input_tokens.confirmed_subtotal == 20
    assert snapshots[-1].telemetry.cost_usd.confirmed_subtotal == 0.02
    assert "private provider body" not in (store.root / controller.reference).read_text(
        encoding="utf-8"
    )
    assert len(list(store.root.rglob("attempt-*.json"))) == 1


@pytest.mark.parametrize(
    "boundary,occurrence",
    [
        ("attempt_created", 1),
        ("request_prepared", 1),
        ("request_prepared", 2),
        ("request_prepared", 3),
        ("response_received", 1),
        ("response_received", 2),
        ("response_received", 3),
        ("json_parsed", 1),
        ("json_parsed", 2),
        ("json_parsed", 3),
        ("json_parsed", 4),
        ("check_completed", 1),
        ("check_completed", 2),
        ("terminal", 1),
    ],
)
def test_interruption_at_each_boundary_leaves_latest_contract_valid_checkpoint(
    tmp_path, boundary, occurrence
):
    store, snapshots, sends, _, _ = run_execution(
        tmp_path, interrupt=boundary, occurrence=occurrence
    )
    paths = list(store.root.rglob("attempt-*.json"))
    assert len(paths) == 1
    saved = Observation.model_validate_json(paths[0].read_text(encoding="utf-8"))
    assert saved == snapshots[-1]
    assert saved.execution.checkpoint_stage == boundary
    if boundary != "terminal":
        assert saved.execution.state == "running"
        assert saved.execution.terminal_outcome is None
    if boundary == "request_prepared":
        assert len(sends) == occurrence - 1
        http = saved.model_calls[-1].http_attempts[-1]
        assert http.delivery == "unknown" and http.usage is None and http.cost_usd.value is None
        assert saved.telemetry.http_attempts == occurrence


def test_interruption_during_send_keeps_delivery_and_billing_unknown(tmp_path):
    _, snapshots, sends, _, _ = run_execution(tmp_path, interrupt="during_send")
    assert len(sends) == 1
    latest = snapshots[-1]
    assert latest.execution.checkpoint_stage == "request_prepared"
    assert latest.model_calls[0].http_attempts[0].delivery == "unknown"
    assert latest.telemetry.tokens.input_tokens.applicability == "unavailable"
    assert latest.telemetry.cost_usd.provenance == "missing"


def test_new_attempt_preserves_incomplete_attempt_bytes_and_rejects_identity_reuse(tmp_path):
    store, snapshots, _, _, _ = run_execution(tmp_path, interrupt="request_prepared")
    path = next(store.root.rglob("attempt-001.json"))
    before = path.read_bytes()
    # Reopening compatibility/plan selection belongs to resume orchestration;
    # this boundary requires its caller to allocate a new attempt identity.
    store.write_observation = RunStore.write_observation.__get__(store)
    catalog = Catalog.load(staples=STAPLES)
    with pytest.raises(CheckpointError):
        AttemptCheckpointer(store, initial_observation(catalog))
    next_attempt = AttemptCheckpointer(store, initial_observation(catalog, execution_attempt=2))
    assert path.read_bytes() == before
    assert next_attempt.observation.execution_attempt == 2
    assert snapshots[-1].telemetry.http_attempts == 1


def test_malformed_json_is_checkpointed_even_when_production_raises(tmp_path):
    _, snapshots, sends, _, _ = run_execution(tmp_path, malformed=True)
    assert len(sends) == 2
    assert snapshots[-1].execution.checkpoint_stage == "json_parsed"
    call = snapshots[-1].model_calls[0]
    assert call.parsing.succeeded is False and call.parsing.error == "invalid JSON"
    assert call.http_attempts[-1].safe_response_text == "{bad"
    assert call.http_attempts[-1].cost_usd.value == 0.01
    assert snapshots[-1].execution.terminal_outcome is None


def test_slow_writes_do_not_change_retry_reask_or_check_decisions(tmp_path):
    fast = run_execution(tmp_path / "fast")
    slow = run_execution(tmp_path / "slow", delay=90)
    assert fast[4] == slow[4]
    assert len(fast[2]) == len(slow[2]) == 3
    assert fast[3].observation.checks == slow[3].observation.checks
    assert slow[3].checkpoint_persistence_s == 90 * len(slow[1])
    assert fast[3].policy_time() == slow[3].policy_time() == 0.75
