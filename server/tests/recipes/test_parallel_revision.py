# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""Concurrent revision calls return the same response as the sequential loop (no network)."""

import json
import threading

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.recipes.policy import RecommendationPolicy
from app.recipes.recommendations import RecommendationService
from recipe_revision.core import APIError, LLMResponse
from recipe_revision.failures import Failure
from tests.conftest import StubVision


def result_for(name):
    if name == "Recipe 20":
        return {
            "can_revise": True,
            "reason": "",
            "changes": [],
            "revised_recipe": {
                "name": "Revised",
                "servings": "4 servings",
                "ingredients": [{"ingredient_id": 1, "name": "Alpha", "quantity_text": None}],
                "steps": [{"step_number": 1, "instruction": "Cook fully", "tip": None}],
            },
        }
    return {"can_revise": False, "reason": "Refused", "changes": [], "revised_recipe": None}


class NamedLLM:
    """Output depends only on the recipe name, so call order cannot change the response."""

    def __init__(self, fail_on=None, barrier=None):
        self.fail_on = fail_on
        self.barrier = barrier
        self.lock = threading.Lock()
        self.names = []

    def generate(self, request):
        name = json.loads(request.user)["original"]["name"]
        with self.lock:
            self.names.append(name)
        if self.barrier is not None:
            self.barrier.wait(timeout=5)  # only passes when all calls are in flight together
        if name == self.fail_on:
            raise APIError("rate limited", failure=Failure("rate_limit", "api_request", 429))
        return LLMResponse(json.dumps({"result": result_for(name)}))


def post(repository, llm, workers):
    service = RecommendationService(
        repository,
        llm_factory=lambda: llm,
        policy=RecommendationPolicy(revision_workers=workers),
    )
    client = TestClient(create_app(StubVision(), repository, recommendations=service))
    return client.post("/recipes/recommendations", json={"ingredient_ids": [1, 2]}).json()


def test_parallel_response_equals_sequential(integration_repository):
    sequential = post(integration_repository, NamedLLM(), 1)
    parallel = post(integration_repository, NamedLLM(), 3)
    assert parallel == sequential
    assert sequential["revision_summary"]["attempted_count"] == 3


def test_parallel_calls_are_in_flight_together(integration_repository):
    llm = NamedLLM(barrier=threading.Barrier(3))
    body = post(integration_repository, llm, 3)
    assert sorted(llm.names) == ["Recipe 20", "Recipe 30", "Recipe 40"]
    assert [e["revision"]["status"] for e in body["recipes"] if e["recipe_id"] in (20, 30, 40)] == [
        "revised",
        "refused",
        "refused",
    ]


def test_shared_failure_response_matches_sequential_semantics(integration_repository):
    sequential_llm, parallel_llm = NamedLLM(fail_on="Recipe 30"), NamedLLM(fail_on="Recipe 30")
    sequential = post(integration_repository, sequential_llm, 1)
    parallel = post(integration_repository, parallel_llm, 3)
    assert parallel == sequential
    entries = {e["recipe_id"]: e["revision"] for e in parallel["recipes"]}
    assert entries[30]["status"] == "failed"
    assert entries[40]["not_attempted_reason"] == "shared_failure"
    assert parallel["revision_summary"]["attempted_count"] == 2
    # The only cost of concurrency: the skipped candidate was still called.
    assert len(sequential_llm.names) == 2 and len(parallel_llm.names) == 3


@pytest.mark.parametrize("workers", [0, 6])
def test_workers_are_validated(workers):
    with pytest.raises(ValueError):
        RecommendationPolicy(revision_workers=workers)
