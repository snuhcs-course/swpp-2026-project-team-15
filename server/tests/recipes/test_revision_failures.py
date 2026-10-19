"""Typed provider failure checks using fake HTTP transports only."""
# AI-generated with Codex (GPT-6.1 Sol)
# 2026-10-17; reviewed by Soohyun An

import json
from io import BytesIO
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

from recipe_revision.adapters import ChatCompletionsLLM
from recipe_revision.core import APIError, RevisionRequest, revise


@pytest.mark.parametrize(
    "status,provider_code,expected,scope",
    [
        (401, None, "authentication", "shared"),
        (403, None, "permission", "shared"),
        (429, None, "rate_limit", "shared"),
        (429, "insufficient_quota", "quota_exceeded", "shared"),
        (429, "quota_exceeded", "quota_exceeded", "shared"),
        (503, None, "provider_unavailable", "shared"),
        (400, "model_not_found", "configuration", "shared"),
        (400, "unknown", "api_error", "individual"),
        (418, None, "api_error", "individual"),
        (400, ["malformed"], "api_error", "individual"),
    ],
)
def test_http_failure_metadata(status, provider_code, expected, scope):
    body = BytesIO(json.dumps({"error": {"code": provider_code, "message": "secret-key"}}).encode())
    failure = HTTPError("https://example.test", status, "secret-key", {}, body)
    transport = Mock(side_effect=failure)
    llm = ChatCompletionsLLM(
        "https://example.test", "mock-model", "secret-key", transport=transport
    )
    with pytest.raises(APIError) as caught:
        llm.generate(RevisionRequest("system", "user"))
    assert caught.value.failure.code == expected
    assert caught.value.failure.scope == scope
    assert caught.value.failure.http_status == status
    assert "secret-key" not in str(caught.value) + caught.value.failure.message
    assert body.closed
    transport.assert_called_once()


@pytest.mark.parametrize(
    "cause,expected",
    [
        (TimeoutError("secret-key"), "timeout"),
        (URLError(TimeoutError("secret-key")), "timeout"),
        (URLError("secret-key"), "connection"),
        (OSError("secret-key"), "connection"),
    ],
)
def test_transport_failure_types(cause, expected):
    transport = Mock(side_effect=cause)
    llm = ChatCompletionsLLM(
        "https://example.test", "mock-model", "secret-key", transport=transport
    )
    with pytest.raises(APIError) as caught:
        llm.generate(RevisionRequest("system", "user"))
    assert caught.value.failure.code == expected
    assert caught.value.failure.stage == "api_request"
    assert caught.value.failure.scope == "individual"
    assert "secret-key" not in str(caught.value)
    transport.assert_called_once()


def test_core_carries_metadata_without_changing_legacy_error_fields(integration_repository):
    recipes, inventory = integration_repository.load_catalog([1], 204)
    failure = HTTPError("https://example.test", 401, "secret-key", {}, BytesIO(b"not json"))
    transport = Mock(side_effect=failure)
    llm = ChatCompletionsLLM(
        "https://example.test", "mock-model", "secret-key", transport=transport
    )
    outcome = revise(recipes[0], inventory, llm)
    assert outcome.status == "api_error"
    assert outcome.error == "LLM HTTP error 401"
    assert outcome.failure_stage == "api_request"
    assert outcome.failure.code == "authentication"
    assert outcome.raw_response is None
