# AI-assisted with Codex, 2026-11-11; reviewed by Soohyun An
# Test reorganization assisted by Codex, 2026-11-15; reviewed by Soohyun An
"""Bounded HTTP requests, pacing, opt-in and response diagnostics."""

import hashlib
import json
from datetime import timedelta
from email.utils import format_datetime

import pytest
import requests

from crawlers.tenkrecipes.tests.support_http import (
    DETAIL_URL,
    FakeResponse,
    client_for,
)


def test_get_requires_live_opt_in_before_transport():
    module, client, transport, _ = client_for(FakeResponse(), live=False)
    with pytest.raises(module.NetworkDisabled):
        client.get(DETAIL_URL)
    assert transport.calls == []


def test_get_passes_bounded_timeouts_identity_and_spaces_request_starts():
    _, client, transport, _ = client_for(FakeResponse(), FakeResponse())
    assert client.get(DETAIL_URL)["status"] == "ok"
    assert client.get(DETAIL_URL)["status"] == "ok"
    assert all(tuple(call["timeout"]) == (10, 30) for call in transport.calls)
    assert transport.calls[1]["start"] - transport.calls[0]["start"] >= 2
    assert all(call["headers"].get("User-Agent", "").strip() for call in transport.calls)


def test_response_preserves_body_and_records_final_url_time_status_and_hash():
    response = FakeResponse(body=b"synthetic original bytes", url=DETAIL_URL + "?observed=1")
    _, client, _, clock = client_for(response)
    result = client.get(DETAIL_URL)
    assert result["body"] == response.content
    attempt = result["attempts"][0]
    assert attempt["source_url"] == DETAIL_URL
    assert attempt["final_url"] == response.url
    assert attempt["fetched_at"] == clock.utcnow().isoformat()
    assert attempt["status_code"] == 200
    assert attempt["sha256"] == hashlib.sha256(response.content).hexdigest()


@pytest.mark.parametrize(
    "failure", [FakeResponse(503), requests.Timeout("timeout"), requests.ConnectionError("lost")]
)
def test_transient_failure_retries_then_succeeds_with_attempt_history(failure):
    _, client, transport, _ = client_for(failure, FakeResponse())
    result = client.get(DETAIL_URL)
    assert result["status"] == "ok"
    assert len(result["attempts"]) == len(transport.calls) == 2
    assert transport.calls[1]["start"] - transport.calls[0]["start"] >= 2


@pytest.mark.parametrize("status", [429, 503])
def test_retry_limit_is_three_total_attempts(status):
    _, client, transport, _ = client_for(*(FakeResponse(status) for _ in range(4)))
    result = client.get(DETAIL_URL)
    assert result["status"] == "failed"
    assert result["reason"] == "retry_exhausted"
    assert len(result["attempts"]) == len(transport.calls) == 3


@pytest.mark.parametrize("header_form", ["seconds", "http_date"])
def test_retry_after_is_respected_without_real_waiting(header_form):
    _, client, transport, clock = client_for(FakeResponse(), FakeResponse())
    header = (
        "7"
        if header_form == "seconds"
        else format_datetime(clock.utcnow() + timedelta(seconds=7), usegmt=True)
    )
    transport.outcomes[0] = FakeResponse(429, headers={"Retry-After": header})
    assert client.get(DETAIL_URL)["status"] == "ok"
    assert transport.calls[1]["start"] - transport.calls[0]["start"] >= 7


@pytest.mark.parametrize(
    ("limits", "reason"),
    [(dict(max_wait=5), "wait_budget_exceeded"), (dict(run_budget=5), "run_budget_exceeded")],
)
def test_retry_wait_over_budget_defers_without_a_premature_retry(limits, reason):
    _, client, transport, clock = client_for(
        FakeResponse(429, headers={"Retry-After": "30"}), FakeResponse(), **limits
    )
    result = client.get(DETAIL_URL)
    assert result["status"] == "deferred"
    assert result["reason"] == reason
    assert len(transport.calls) == len(result["attempts"]) == 1
    assert clock.elapsed < 30


@pytest.mark.parametrize("status", [401, 403])
def test_access_denial_stops_without_retry_or_identity_rotation(status):
    _, client, transport, _ = client_for(FakeResponse(status), FakeResponse())
    result = client.get(DETAIL_URL)
    assert result["status"] == "blocked"
    assert result["reason"] == "access_denied"
    assert len(transport.calls) == 1


def test_success_status_challenge_is_blocked_instead_of_recipe_success():
    body = b'<html><title>Just a moment...</title><form id="challenge-form"></form></html>'
    _, client, transport, _ = client_for(FakeResponse(body=body), FakeResponse())
    result = client.get(DETAIL_URL)
    assert result["status"] == "blocked"
    assert result["reason"] == "challenge"
    assert len(transport.calls) == 1


def test_nonretryable_http_failure_does_not_consume_three_attempts():
    _, client, transport, _ = client_for(FakeResponse(404), FakeResponse())
    result = client.get(DETAIL_URL)
    assert result["status"] == "failed"
    assert result["reason"] == "http_error"
    assert len(transport.calls) == 1


def test_attempt_diagnostics_do_not_persist_response_cookies_or_exception_secrets(capsys):
    _, client, _, _ = client_for(
        requests.ConnectionError("Cookie: session=synthetic-secret"),
        FakeResponse(headers={"Set-Cookie": "session=synthetic-secret"}),
    )
    result = client.get(DETAIL_URL)
    assert result["status"] == "ok"
    assert "synthetic-secret" not in json.dumps(result["attempts"])
    captured = capsys.readouterr()
    assert "synthetic-secret" not in captured.out + captured.err
