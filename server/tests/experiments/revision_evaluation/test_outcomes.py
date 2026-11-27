# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Offline outcome classification against frozen artifacts and production execution."""

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
from experiments.revision_evaluation.contract import CheckEvent, Observation
from experiments.revision_evaluation.generate_contract import fixture_observations
from experiments.revision_evaluation.outcomes import classify_terminal, persist_terminal
from experiments.revision_evaluation.persistence import PersistenceError, RunStore
from experiments.revision_evaluation.transport import CheckpointError

from app.dishes.catalog import Catalog
from app.dishes.errors import MODEL_NOT_CONFIGURED, DishLLMError
from app.dishes.llm import DishLLM
from app.dishes.recipes import RecipeStore
from app.dishes.schemas import ReviseResponse, SourceRecipe
from tests.dishes.test_dishes import STAPLES
from tests.dishes.test_revision import GOOD, RECIPE
from tests.experiments.revision_evaluation.test_checkpointing import initial_observation


@pytest.mark.parametrize("name", list(fixture_observations()))
def test_every_frozen_fixture_has_the_same_outcome_and_source(name):
    value = Observation.model_validate(fixture_observations()[name])
    before = value.model_dump(by_alias=True)
    final = value.execution.final_service_response
    response = ReviseResponse.model_validate(final) if final is not None else None
    error = (
        DishLLMError(value.execution.sanitized_error) if value.execution.sanitized_error else None
    )
    result = classify_terminal(value, response=response, error=error)
    if value.execution.state == "completed":
        assert (result.outcome, result.source) == (
            value.execution.terminal_outcome,
            value.execution.outcome_source,
        )
    else:
        assert result is None
    assert value.model_dump(by_alias=True) == before


@pytest.mark.parametrize(
    "error",
    [
        CheckpointError("storage-secret"),
        PersistenceError("storage-secret"),
        KeyboardInterrupt(),
        RuntimeError("unexpected-secret"),
        DishLLMError(MODEL_NOT_CONFIGURED),
    ],
)
def test_operational_and_configuration_failures_propagate_without_terminal_outcome(error):
    value = Observation.model_validate(fixture_observations()["resumed__r03/attempt-001.json"])
    with pytest.raises(type(error)) as caught:
        classify_terminal(value, error=error)
    assert caught.value is error
    assert value.execution.terminal_outcome is None


def test_missing_completion_or_uncertain_prepared_request_is_not_a_terminal_failure():
    value = Observation.model_validate(fixture_observations()["resumed__r03/attempt-001.json"])
    value.execution.state = "running"
    assert classify_terminal(value) is None
    assert (
        classify_terminal(value, error=DishLLMError("The model service could not be reached"))
        is None
    )


def test_interrupted_attempt_cannot_be_relabelled_by_a_later_response():
    fixtures = fixture_observations()
    value = Observation.model_validate(fixtures["resumed__r03/attempt-001.json"])
    response = ReviseResponse.model_validate(
        fixtures["resumed__r03/attempt-002.json"]["execution"]["final_service_response"]
    )
    assert classify_terminal(value, response=response) is None
    assert (
        classify_terminal(value, error=DishLLMError("The model service could not be reached"))
        is None
    )


def test_conflicting_completion_evidence_is_rejected():
    value = Observation.model_validate(fixture_observations()["unchanged__r01/attempt-001.json"])
    response = ReviseResponse.model_validate(value.execution.final_service_response)
    with pytest.raises(ValueError, match="both a response and an error"):
        classify_terminal(value, response=response, error=DishLLMError("model failure"))


def test_unknown_model_error_message_is_fixed_not_copied():
    value = Observation.model_validate(fixture_observations()["api-error__r01/attempt-001.json"])
    result = classify_terminal(value, error=DishLLMError("Authorization: Bearer private-key"))
    assert result.outcome == "api_error"
    assert result.error == "model call failed"


def test_known_production_model_error_message_is_preserved():
    value = Observation.model_validate(fixture_observations()["api-error__r01/attempt-001.json"])
    message = "The model service could not be reached"
    assert classify_terminal(value, error=DishLLMError(message)).error == message


def test_failed_reask_uses_last_call_not_the_successful_initial_http_response():
    value = Observation.model_validate(fixture_observations()["check-failed__r01/attempt-001.json"])
    failed = fixture_observations()["api-error__r01/attempt-001.json"]["model_calls"][0]
    failed["index"], failed["purpose"] = 2, "reask"
    value.model_calls[-1] = type(value.model_calls[-1]).model_validate(failed)
    result = classify_terminal(value, error=DishLLMError("The model service could not be reached"))
    assert (result.outcome, result.source) == ("api_error", "transport")


def test_check_owned_refusal_is_distinct_from_a_model_refusal():
    value = Observation.model_validate(fixture_observations()["check-failed__r01/attempt-001.json"])
    response = ReviseResponse.model_validate(
        fixture_observations()["refused-prescreen__r01/attempt-001.json"]["execution"][
            "final_service_response"
        ]
    )
    value.checks[-1] = CheckEvent(
        phase="final", result="refusal_needed", code=None, message="missing main"
    )
    assert classify_terminal(value, response=response).source == "production_check"
    value.checks[-1] = CheckEvent(phase="final", result="not_run", code=None, message=None)
    assert classify_terminal(value, response=response).source == "model"


def test_deterministic_parse_failure_does_not_override_a_production_success():
    value = Observation.model_validate(fixture_observations()["resumed__r03/attempt-002.json"])
    response = ReviseResponse.model_validate(value.execution.final_service_response)
    # Production can salvage a token-limited response; scoring must not relabel it.
    value.model_calls[0].parsing.succeeded = False
    value.deterministic_evaluation.answers[0].structure_valid = False
    result = classify_terminal(value, response=response)
    assert (result.outcome, result.source) == ("revised", "model")


@pytest.mark.parametrize(
    "case,expected_outcome,expected_source",
    [
        ("unchanged", "unchanged", "no_change"),
        ("prescreen", "refused", "prescreen"),
        ("revised", "revised", "model"),
        ("recovered", "revised", "model"),
        ("double_failure", "check_failed", "production_check"),
        ("model_refusal", "refused", "model"),
        ("bad_json", "response_error", "response"),
        ("array", "response_error", "response"),
        ("invalid_body", "response_error", "response"),
        ("transport", "api_error", "transport"),
        ("429", "api_error", "transport"),
        ("400", "api_error", "transport"),
        ("500", "api_error", "transport"),
    ],
)
def test_production_paths_persist_the_classified_result_without_losing_trace(
    tmp_path, case, expected_outcome, expected_source
):
    catalog = Catalog.load(staples=STAPLES)
    initial = initial_observation(catalog)
    ingredients = ["밥", "김치"]
    if case == "unchanged":
        ingredients = ["밥", "김치", "대파", "달걀"]
    elif case == "prescreen":
        ingredients = ["밥"]
    initial.input.supplied_ingredients = ingredients
    initial.input.availability = [
        catalog.status(row.name, catalog.owned(ingredients))
        for row in initial.input.original_recipe.ingredients
    ]
    store = RunStore(tmp_path, "checkpoint-run")
    controller = AttemptCheckpointer(store, initial, clock=lambda: 0)
    sends = []

    def handle(request):
        sends.append(request)
        if case == "transport":
            raise httpx.ConnectError("provider-private-secret")
        if case in ("400", "429", "500"):
            return httpx.Response(int(case), json={"error": "provider-private-secret"})
        if case == "invalid_body":
            return httpx.Response(200, content=b"not a provider JSON envelope")
        answer = deepcopy(GOOD)
        if case == "double_failure" or (case == "recovered" and len(sends) == 1):
            answer["changes"] = []
        if case == "model_refusal":
            answer = {"can_revise": False, "refusal_reason": "안전한 조리가 어려워요."}
        text = "{bad" if case == "bad_json" else "[]" if case == "array" else json.dumps(answer)
        return httpx.Response(
            200,
            json={
                "choices": [{"finish_reason": "stop", "message": {"content": text}}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 20, "cost": 0.01},
            },
        )

    transport = CheckpointTransport(httpx.MockTransport(handle), checkpointer=controller)
    model = CheckpointModelCallRecorder(
        DishLLM("test-key", transport=transport, retry_waits=(), clock=controller.policy_time),
        checkpointer=controller,
    )
    recipes = RecipeStore({RECIPE["dish_id"]: SourceRecipe.model_validate(deepcopy(RECIPE))})
    reviser = CheckpointReviser(catalog, catalog, model, recipes, checkpointer=controller)
    response, error = None, None
    try:
        response = reviser.revise(RECIPE["dish_id"], ingredients)
    except DishLLMError as caught:
        error = caught
    evidence = deepcopy((controller.observation.model_calls, controller.observation.checks))
    result = persist_terminal(controller, response=response, error=error)
    assert (result.outcome, result.source) == (expected_outcome, expected_source)
    saved_text = (store.root / controller.reference).read_text(encoding="utf-8")
    saved = Observation.model_validate_json(saved_text)
    assert saved.execution.state == "completed"
    assert (saved.execution.terminal_outcome, saved.execution.outcome_source) == (
        expected_outcome,
        expected_source,
    )
    assert (saved.model_calls, saved.checks) == evidence
    assert saved.execution.final_service_response == (response.model_dump() if response else None)
    assert "provider-private-secret" not in saved_text


def test_incomplete_finalization_does_not_write_or_increase_revision(tmp_path):
    store = RunStore(tmp_path, "checkpoint-run")
    controller = AttemptCheckpointer(store, initial_observation(Catalog.load(staples=STAPLES)))
    path = store.root / controller.reference
    before = path.read_bytes()
    assert persist_terminal(controller) is None
    assert path.read_bytes() == before
    with pytest.raises(CheckpointError):
        persist_terminal(controller, error=CheckpointError("private-storage-detail"))
    assert path.read_bytes() == before
