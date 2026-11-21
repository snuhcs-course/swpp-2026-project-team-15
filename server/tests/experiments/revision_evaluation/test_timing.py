# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Offline regression checks for shared Revision/retry clocks and checkpoint timing."""

import json
from copy import deepcopy

import httpx
import pytest
from experiments.revision_evaluation.reviser import TracedReviser
from experiments.revision_evaluation.tracing import LogicalModelCallRecorder
from experiments.revision_evaluation.transport import RecordingTransport

from app.dishes.catalog import Catalog
from app.dishes.errors import DishLLMError
from app.dishes.http import APP_READ_SECONDS
from app.dishes.llm import CALL_BUDGET, DishLLM
from app.dishes.recipes import RecipeStore
from app.dishes.revision import Reviser
from app.dishes.schemas import SourceRecipe
from tests.dishes.test_dishes import STAPLES
from tests.dishes.test_revision import GOOD, RECIPE


def run_execution(
    *, traced, checkpoint_delay=0, call_duration=0, api_error=False, retry=False
):
    """Run production call/retry/check code with injected clocks and mock HTTP."""
    now, sends = [0.0], []

    def clock():
        return now[0]

    def save(call):
        now[0] += checkpoint_delay

    def handle(request):
        sends.append({"at": now[0], "timeout": request.extensions.get("timeout")})
        now[0] += call_duration
        if api_error:
            raise httpx.ConnectError("provider-private-detail")
        if retry and len(sends) == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        answer_number = len(sends) - int(retry)
        answer = {**GOOD, "changes": []} if answer_number == 1 else GOOD
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(answer, ensure_ascii=False),
                        },
                    }
                ],
            },
        )

    mock = httpx.MockTransport(handle)
    transport = RecordingTransport(mock, checkpoint=save, clock=clock) if traced else mock
    policy_clock = transport.policy_time if traced else clock
    model = LogicalModelCallRecorder(
        DishLLM("test-key", transport=transport, retry_waits=(0,), clock=policy_clock)
    )
    catalog = Catalog.load(staples=STAPLES)
    store = RecipeStore({RECIPE["dish_id"]: SourceRecipe.model_validate(deepcopy(RECIPE))})
    reviser = (TracedReviser if traced else Reviser)(
        catalog, catalog, model, store, clock=policy_clock
    )
    error = None
    result = None
    try:
        result = reviser.revise(RECIPE["dish_id"], ["밥", "김치"])
    except DishLLMError as caught:
        error = str(caught)
    return result, error, model, sends, transport


def test_reask_is_suppressed_when_production_time_budget_is_exhausted():
    elapsed = APP_READ_SECONDS - CALL_BUDGET + 0.01
    plain = run_execution(traced=False, call_duration=elapsed)
    traced = run_execution(traced=True, call_duration=elapsed, checkpoint_delay=90)
    assert plain[0] == traced[0] and traced[0].status == "failed"
    assert plain[1] is traced[1] is None
    assert len(plain[2].calls) == len(traced[2].calls) == 1
    assert len(plain[3]) == len(traced[3]) == 1
    assert traced[4].checkpoint_persistence_s == 180


def test_api_error_preserves_production_message_and_call_counts():
    plain = run_execution(traced=False, api_error=True)
    traced = run_execution(traced=True, api_error=True, checkpoint_delay=90)
    assert plain[0] is traced[0] is None
    assert plain[1] == traced[1] == "The model service could not be reached"
    assert len(plain[2].calls) == len(traced[2].calls) == 1
    assert len(plain[3]) == len(traced[3]) == 1
    assert traced[2].calls[0].http_attempts[0].state == "transport_error"


def test_real_provider_time_still_exhausts_retry_budget():
    plain = run_execution(traced=False, retry=True, call_duration=CALL_BUDGET + 0.01)
    traced = run_execution(
        traced=True, retry=True, call_duration=CALL_BUDGET + 0.01, checkpoint_delay=90,
    )
    assert plain[0] is traced[0] is None
    assert plain[1] == traced[1] == "The model service is temporarily unavailable"
    assert len(plain[3]) == len(traced[3]) == 1
    assert len(plain[2].calls) == len(traced[2].calls) == 1
    assert traced[4].checkpoint_persistence_s == 180


@pytest.mark.parametrize("retry", [False, True])
def test_slow_checkpoints_preserve_retry_reask_and_timeout_decisions(retry):
    plain = run_execution(traced=False, retry=retry, call_duration=0.25)
    traced = run_execution(
        traced=True,
        checkpoint_delay=APP_READ_SECONDS,
        retry=retry,
        call_duration=0.25,
    )
    assert plain[0].status == "revised"
    assert len(plain[2].calls) == 2
    assert len(plain[3]) == 2 + int(retry)
    assert traced[0] == plain[0] and traced[1] is plain[1] is None
    assert len(traced[2].calls) == len(plain[2].calls)
    assert len(traced[3]) == len(plain[3])
    assert [send["timeout"] for send in traced[3]] == [send["timeout"] for send in plain[3]]
    assert traced[4].checkpoint_persistence_s == 2 * len(traced[3]) * APP_READ_SECONDS
    assert all(
        attempt.provider_round_trip_s == 0.25
        for call in traced[2].calls for attempt in call.http_attempts
    )
    # Observed wall time includes persistence; policy time retains actual HTTP time.
    assert traced[4].policy_time() == 0.25 * len(traced[3])


def test_separate_execution_instances_start_logical_call_numbering_at_one():
    first = run_execution(traced=True)
    second = run_execution(traced=True)
    assert first[2] is not second[2]
    assert [call.index for call in first[2].calls] == [1, 2]
    assert [call.index for call in second[2].calls] == [1, 2]
    assert first[2].calls[0].purpose == second[2].calls[0].purpose == "initial"
    # A future Runner must construct these instances per execution attempt; this
    # test proves isolation when composed correctly, not that orchestration exists.
