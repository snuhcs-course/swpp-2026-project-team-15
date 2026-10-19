"""End-to-end recipe orchestration using temporary SQLite and scripted LLMs only."""
# AI-generated with Codex (GPT-6.1 Sol)
# 2026-10-17; reviewed by Soohyun An

import json
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app, create_app_from_env
from app.recipes.dependencies import get_recommendation_service
from app.recipes.policy import RecommendationPolicy
from app.recipes.providers import revision_factory
from app.recipes.recommendations import RecommendationService
from app.recipes.schemas import RecommendationsRequest
from app.recipes.service import SourceUnavailable
from recipe_revision.core import APIError, LLMResponse, ResponseFormatError
from recipe_revision.failures import Failure
from tests.conftest import StubVision


class ScriptedLLM:
    """Record exact inputs and produce scripted outcomes; never access a transport."""

    def __init__(self, actions=()):
        self.actions = list(actions)
        self.requests = []

    def generate(self, request):
        context = json.loads(request.user)
        self.requests.append(context)
        action = self.actions.pop(0) if self.actions else "refused"
        if isinstance(action, Exception):
            raise action
        if action == "malformed":
            return LLMResponse("secret-key malformed JSON")
        if action == "revised":
            result = {
                "can_revise": True,
                "reason": "",
                "changes": [],
                "revised_recipe": {
                    "name": "Mock revised",
                    "servings": "4 servings",
                    "ingredients": [{"ingredient_id": 1, "name": "Alpha", "quantity_text": None}],
                    "steps": [{"step_number": 1, "instruction": "Cook fully", "tip": None}],
                },
            }
        else:
            result = {
                "can_revise": False,
                "reason": "Mock refusal",
                "changes": [],
                "revised_recipe": None,
            }
        return LLMResponse(json.dumps({"result": result}))


def client_for(repository, llm=None, *, factory=None, policy=None):
    service = RecommendationService(
        repository,
        llm_factory=factory if factory is not None else lambda: llm,
        policy=policy or RecommendationPolicy(),
    )
    return TestClient(create_app(StubVision(), repository, recommendations=service))


def test_full_list_and_priority_are_distinct(integration_repository):
    llm = ScriptedLLM(["revised", "refused", "refused"])
    response = client_for(integration_repository, llm).post(
        "/recipes/recommendations", json={"ingredient_ids": [1, 2, 1]}
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["recipes"]) == 6
    assert [context["original"]["recipe_id"] for context in llm.requests] == [20, 30, 40]
    assert body["revision_summary"] == {
        "limit": 3,
        "selected_count": 3,
        "attempted_count": 3,
        "stopped_error": None,
    }
    assert body["assumed_ingredient_ids"] == [204]
    entries = {entry["recipe_id"]: entry for entry in body["recipes"]}
    assert entries[20]["revision"]["status"] == "revised"
    assert entries[20]["revision"]["result"]["reason"] == ""
    assert entries[30]["revision"]["status"] == "refused"
    assert entries[10]["revision"]["not_attempted_reason"] == "outside_revision_limit"
    assert len(entries[20]["original"]["ingredients"]) == 5
    assert {row["ingredient_id"] for row in llm.requests[0]["inventory"]} == {1, 2, 204}
    assert "secret-key" not in response.text


@pytest.mark.parametrize(
    "failure,code,stage",
    [
        (
            APIError("secret-key", failure=Failure("timeout", "api_request")),
            "timeout",
            "api_request",
        ),
        (
            APIError("secret-key", failure=Failure("connection", "api_request")),
            "connection",
            "api_request",
        ),
        (
            ResponseFormatError("secret-key", stage="provider_response"),
            "response_format",
            "provider_response",
        ),
        ("malformed", "response_format", "response_parsing"),
        (RuntimeError("secret-key"), "internal", "revision"),
        (APIError("secret-key"), "api_error", "api_request"),
    ],
)
def test_individual_errors_continue_without_backfill(
    integration_repository, failure, code, stage, caplog
):
    llm = ScriptedLLM([failure, "revised", "refused"])
    response = client_for(integration_repository, llm).post(
        "/recipes/recommendations", json={"ingredient_ids": [1, 2]}
    )
    assert response.status_code == 200
    entries = {row["recipe_id"]: row["revision"] for row in response.json()["recipes"]}
    assert entries[20]["status"] == "failed"
    assert entries[20]["error"]["code"] == code
    assert entries[20]["error"]["stage"] == stage
    assert entries[30]["status"] == "revised"
    assert entries[40]["status"] == "refused"
    assert len(llm.requests) == 3
    assert entries[10]["status"] == "not_attempted"
    assert "secret-key" not in response.text + caplog.text


@pytest.mark.parametrize(
    "code,status",
    [
        ("authentication", 401),
        ("permission", 403),
        ("configuration", 400),
        ("rate_limit", 429),
        ("quota_exceeded", 429),
        ("provider_unavailable", 503),
    ],
)
def test_shared_failure_retains_success_and_is_request_scoped(integration_repository, code, status):
    llm = ScriptedLLM(
        ["revised", APIError("secret-key", failure=Failure(code, "api_request", status))]
    )
    client = client_for(integration_repository, llm)
    response = client.post("/recipes/recommendations", json={"ingredient_ids": [1, 2]})
    body = response.json()
    assert response.status_code == 200
    entries = {row["recipe_id"]: row["revision"] for row in body["recipes"]}
    assert entries[20]["status"] == "revised"
    assert entries[30]["status"] == "failed"
    assert entries[40]["not_attempted_reason"] == "shared_failure"
    assert entries[10]["not_attempted_reason"] == "outside_revision_limit"
    assert body["revision_summary"]["attempted_count"] == 2
    assert body["revision_summary"]["stopped_error"]["code"] == code
    assert len(llm.requests) == 2
    assert "secret-key" not in response.text
    next_response = client.post("/recipes/recommendations", json={"ingredient_ids": [1, 2]})
    assert next_response.json()["revision_summary"]["attempted_count"] == 3
    assert next_response.json()["revision_summary"]["stopped_error"] is None


def test_configuration_failure_does_not_fabricate_attempts(integration_repository):
    factory = Mock(side_effect=ValueError("secret-key"))
    response = client_for(integration_repository, factory=factory).post(
        "/recipes/recommendations", json={"ingredient_ids": [1, 2]}
    )
    summary = response.json()["revision_summary"]
    assert response.status_code == 200
    assert summary["attempted_count"] == 0
    assert summary["stopped_error"]["code"] == "configuration"
    assert len(response.json()["recipes"]) == 6
    assert (
        sum(
            row["revision"]["not_attempted_reason"] == "shared_failure"
            for row in response.json()["recipes"]
        )
        == 3
    )
    assert "secret-key" not in response.text
    factory.assert_called_once()


@pytest.mark.parametrize("ids", [[], [4], [204], [6]])
def test_no_candidates_skips_provider_and_synonyms(integration_repository, ids):
    factory = Mock(side_effect=AssertionError("Provider must not be constructed"))
    response = client_for(integration_repository, factory=factory).post(
        "/recipes/recommendations", json={"ingredient_ids": ids}
    )
    assert response.status_code == 200
    assert response.json()["recipes"] == []
    factory.assert_not_called()


@pytest.mark.parametrize(
    "body",
    [
        {"ingredient_ids": [999]},
        {"ingredient_ids": [True]},
        {"ingredient_ids": [1], "revision_limit": 6},
    ],
)
def test_invalid_input_before_provider(integration_repository, body):
    factory = Mock()
    assert (
        client_for(integration_repository, factory=factory)
        .post("/recipes/recommendations", json=body)
        .status_code
        == 422
    )
    factory.assert_not_called()


def test_internal_value_error_is_not_an_input_error(integration_repository):
    integration_repository.load_catalog = Mock(side_effect=ValueError("internal detail"))
    factory = Mock()
    service = RecommendationService(integration_repository, llm_factory=factory)
    with TestClient(
        create_app(StubVision(), integration_repository, recommendations=service),
        raise_server_exceptions=False,
    ) as client:
        response = client.post("/recipes/recommendations", json={"ingredient_ids": [1]})
    assert response.status_code == 500
    assert "internal detail" not in response.text
    factory.assert_not_called()


def test_db_failure_is_503_before_provider(integration_repository):
    integration_repository.load_catalog = Mock(side_effect=SourceUnavailable("secret-key"))
    factory = Mock()
    response = client_for(integration_repository, factory=factory).post(
        "/recipes/recommendations", json={"ingredient_ids": [1]}
    )
    assert response.status_code == 503
    assert "secret-key" not in response.text
    factory.assert_not_called()


def test_policy_and_service_dependency_override(integration_repository):
    llm = ScriptedLLM()
    policy = RecommendationPolicy(default_revision_limit=1, maximum_revision_limit=2)
    client = TestClient(create_app(StubVision(), integration_repository))
    service = RecommendationService(integration_repository, policy=policy, llm_factory=lambda: llm)
    client.app.dependency_overrides[get_recommendation_service] = lambda: service
    response = client.post("/recipes/recommendations", json={"ingredient_ids": [1, 2, 4]})
    assert response.json()["revision_summary"]["attempted_count"] == 1
    assert {row["ingredient_id"] for row in llm.requests[0]["inventory"]} == {1, 2, 4, 204}
    assert (
        client.post(
            "/recipes/recommendations",
            json={
                "ingredient_ids": [1, 2],
                "revision_limit": 3,
            },
        ).status_code
        == 422
    )
    # Selection is capped by candidate count, not always by the requested limit.
    smaller = service.recommend(RecommendationsRequest(ingredient_ids=[3], revision_limit=2))
    assert smaller.revision_summary.selected_count == 1


def test_default_mock_and_openapi(integration_repository, monkeypatch):
    monkeypatch.setattr(
        "urllib.request.OpenerDirector.open", Mock(side_effect=AssertionError("Network"))
    )
    client = TestClient(create_app(StubVision(), integration_repository))
    response = client.post("/recipes/recommendations", json={"ingredient_ids": [1, 2]})
    assert response.status_code == 200
    assert "MOCK ONLY" in response.text
    paths = client.get("/openapi.json").json()["paths"]
    assert "/recipes/recommendations" in paths and "/recipes/recommend" in paths
    settings = Settings.from_env({})
    assert settings.vision_provider == settings.revision_provider == "mock"
    assert revision_factory(settings)().generate(None).text
    for env in ({"REVISION_PROVIDER": "live"}, {"REVISION_PROVIDER": "invalid"}):
        factory = revision_factory(Settings.from_env(env))
        with pytest.raises(ValueError):
            factory()


def test_environment_factory_wires_lazy_revision_and_independent_vision(integration_db):
    settings = Settings.from_env(
        {
            "RECIPE_DB_PATH": str(integration_db),
            "VISION_PROVIDER": "mock",
            "REVISION_PROVIDER": "live",
        }
    )
    with patch("app.main.Settings.from_env", return_value=settings):
        app = create_app_from_env()
    try:
        with TestClient(app) as client:
            assert client.get("/health").status_code == 200
            empty = client.post("/recipes/recommendations", json={"ingredient_ids": []})
            assert empty.json()["revision_summary"]["stopped_error"] is None
            response = client.post("/recipes/recommendations", json={"ingredient_ids": [1, 2]})
            assert response.status_code == 200
            assert response.json()["revision_summary"]["stopped_error"]["code"] == "configuration"
            assert response.json()["revision_summary"]["attempted_count"] == 0
    finally:
        app.state.recipe_repository._engine.dispose()
