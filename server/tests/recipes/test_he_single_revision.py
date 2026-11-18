"""AI-assisted selected recipe regressions, 2026-11-10; human review pending."""

import re
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.recipes.policy import RecommendationPolicy
from app.recipes.recommendations import RecommendationService
from recipe_revision.seasoning import ASSUME_ALL, ASSUME_NONE
from tests.conftest import StubVision
from tests.recipes.test_recommendations import ScriptedLLM


def make_single_client(repository, llm, *, factory=None, retry=False, policy=None):
    service = RecommendationService(
        repository,
        policy=policy or RecommendationPolicy(prescreen="off", retry_on_rejection=retry),
        llm_factory=factory if factory is not None else lambda: llm,
    )
    return TestClient(create_app(StubVision(), repository, recommendations=service))


def test_capability_does_not_construct_or_call_a_model(integration_repository):
    def forbidden():
        raise AssertionError("Free capability probe must not construct a provider")

    client = make_single_client(integration_repository, None, factory=forbidden)
    response = client.get("/recipes/revision-capabilities")
    assert response.status_code == 200
    assert response.json()["selected_recipe_supported"] is True


def test_only_selected_recipe_is_sent_once_and_original_is_returned(integration_repository):
    llm = ScriptedLLM(["refused"])
    response = make_single_client(integration_repository, llm).post(
        "/recipes/40/revision", json={"ingredients": ["Alpha", "Beta", "Salt"]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recipe_id"] == body["original"]["recipe_id"] == 40
    assert body["revision"]["status"] == "refused"
    assert [row["original"]["name"] for row in llm.requests] == ["Recipe 40"]


def test_missing_id_and_unregistered_names_make_no_model_call(integration_repository):
    llm = ScriptedLLM(["refused"])
    client = make_single_client(integration_repository, llm)
    assert client.post("/recipes/9999/revision", json={"ingredients": ["Alpha"]}).status_code == 404
    unknown = client.post("/recipes/40/revision", json={"ingredients": ["Alpha", "Unknown"]})
    assert unknown.status_code == 422
    assert unknown.json()["detail"]["code"] == "unregistered_ingredients"
    assert unknown.json()["detail"]["names"] == ["Unknown"]
    assert llm.requests == []


def test_unknown_omission_requires_explicit_request_flag(integration_repository):
    llm = ScriptedLLM(["refused"])
    response = make_single_client(integration_repository, llm).post(
        "/recipes/40/revision",
        json={"ingredients": ["Alpha", "Unknown"], "ignore_unregistered": True},
    )
    assert response.status_code == 200
    assert len(llm.requests) == 1
    assert "Unknown" not in str(llm.requests[0])


def test_configuration_failure_is_sanitized_and_keeps_original(integration_repository):
    def broken():
        raise ValueError("secret-credential-value")

    response = make_single_client(integration_repository, None, factory=broken).post(
        "/recipes/40/revision", json={"ingredients": ["Alpha"]}
    )
    assert response.status_code == 200
    assert response.json()["original"]["recipe_id"] == 40
    assert response.json()["revision"]["error"]["code"] == "configuration"
    assert "secret-credential-value" not in response.text


def test_selected_route_never_uses_policy_automatic_retry(integration_repository):
    llm = ScriptedLLM(["malformed"])
    response = make_single_client(integration_repository, llm, retry=True).post(
        "/recipes/40/revision", json={"ingredients": ["Alpha"]}
    )
    assert response.status_code == 200
    assert response.json()["revision"]["status"] == "failed"
    assert len(llm.requests) == 1


def test_success_retains_original_and_returns_validated_revised_recipe(integration_repository):
    llm = ScriptedLLM(["revised"])
    response = make_single_client(integration_repository, llm).post(
        "/recipes/30/revision", json={"ingredients": ["Alpha", "Salt"]}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["original"]["recipe_id"] == 30
    assert body["original"]["name"] == "Recipe 30"
    assert body["revision"]["status"] == "revised"
    assert body["revision"]["result"]["revised_recipe"]["ingredients"]
    assert len(llm.requests) == 1


def test_excluded_manufacturing_recipe_is_not_sent(integration_db, integration_repository):
    with sqlite3.connect(integration_db) as db:
        db.execute("UPDATE recipe SET name='된장' WHERE recipe_id=40")
    llm = ScriptedLLM(["refused"])
    response = make_single_client(integration_repository, llm).post(
        "/recipes/40/revision", json={"ingredients": ["Alpha"]}
    )
    assert response.status_code == 404
    assert llm.requests == []


def test_selected_route_shares_paid_gateway_limit_and_timeout():
    config = (Path(__file__).resolve().parents[3] / "deploy" / "nginx.conf").read_text()
    match = re.search(r"location ~ (\S+) \{([^}]+)", config)
    assert match is not None
    assert re.fullmatch(match[1], "/recipes/40/revision")
    assert "limit_req zone=ai" in match[2]
    assert "proxy_read_timeout 210s" in match[2]


@pytest.mark.parametrize("spelling", ["40", "+40", "40.0"])
def test_every_accepted_id_spelling_has_the_same_gateway_limit(integration_repository, spelling):
    llm = ScriptedLLM(["refused"])
    response = make_single_client(integration_repository, llm).post(
        f"/recipes/{spelling}/revision", json={"ingredients": ["Alpha"]}
    )
    assert response.status_code == 200
    assert response.json()["recipe_id"] == 40
    config = (Path(__file__).resolve().parents[3] / "deploy" / "nginx.conf").read_text()
    pattern = re.search(r"location ~ (\S+) \{", config).group(1)
    assert re.fullmatch(pattern, f"/recipes/{spelling}/revision")


@pytest.mark.parametrize("seasonings,missing", [(ASSUME_ALL, []), (ASSUME_NONE, ["Salt"])])
def test_original_shortages_share_the_revision_seasoning_policy(
    integration_repository, seasonings, missing
):
    policy = RecommendationPolicy(prescreen="off", seasonings=seasonings)
    response = make_single_client(
        integration_repository, ScriptedLLM(["refused"]), policy=policy
    ).post("/recipes/40/revision", json={"ingredients": ["Alpha"]})
    assert response.status_code == 200
    assert [row["name"] for row in response.json()["original_missing"]] == missing
