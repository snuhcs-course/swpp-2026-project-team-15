# AI-generated initial implementation with Codex (GPT-6), 2026-11-06; reviewed by Ahyoon Choi.

"""Offline tests for Pixabay API behavior.

Cover request parameters, ranking, retries, rate limits, and forced-refresh safeguards.
"""

import json
from datetime import UTC, datetime, timedelta

import pytest
import requests
import search
from models import Recipe


class FakeResponse:
    """Small response double exposing only the requests.Response interface search_recipe uses."""

    def __init__(self, payload=None, *, status_code=200, headers=None):
        """Set a deterministic body, status, and rate-limit metadata.

        This avoids network access while exposing the response attributes the search code consumes.
        """
        self.payload = payload or {}
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        """Return the preset decoded API payload exactly as requests.Response.json would."""
        return self.payload

    def raise_for_status(self):
        """Raise requests.HTTPError for error statuses so retry/error behavior is realistic."""
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """Serve queued response objects or exceptions and retain every outbound API call."""

    def __init__(self, responses):
        """Store deterministic outcomes for each request attempt in order."""
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        """Record URL/parameters/timeout, then return or raise the next queued outcome."""
        self.calls.append((url, kwargs))
        outcome = self.responses.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _write_cache(path, *, fetched_at=None, query="soup", hits=None):
    """Write a valid recent cache entry that tests can use to exercise reuse or forced refresh."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "fetched_at": (fetched_at or datetime.now(UTC)).isoformat(),
                "query": query,
                "lang": search.SEARCH_LANGUAGE,
                "hits": [] if hits is None else hits,
            }
        ),
        encoding="utf-8",
    )


def _hit(identifier, tags):
    """Build the subset of Pixabay response fields needed to test normalization and ranking."""
    return {
        "id": identifier,
        "pageURL": f"https://pixabay.test/{identifier}",
        "webformatURL": f"https://images.test/{identifier}.jpg",
        "tags": tags,
        "user": "photographer",
        "user_id": 12,
        "imageWidth": 1200,
        "imageHeight": 800,
    }


def test_valid_cache_avoids_pixabay_api_request(tmp_path, monkeypatch):
    """Return fresh matching hits directly from disk without requiring a key or calling HTTP."""
    cache_file = tmp_path / "7.json"
    expected_hits = [_hit(2, "soup")]
    _write_cache(cache_file, hits=expected_hits)
    session = FakeSession([])
    monkeypatch.setattr(search, "_pixabay_key", lambda: pytest.fail("key should not be read"))

    hits, cached = search.search_recipe(Recipe(7, "Soup", "soup"), tmp_path, session=session)

    assert hits == expected_hits
    assert cached is True
    assert session.calls == []


def test_force_refresh_of_recent_cache_requires_confirmation(tmp_path, monkeypatch):
    """Block a recent-cache refresh before credentials or HTTP are used unless confirmed."""
    _write_cache(tmp_path / "7.json")
    session = FakeSession([])
    monkeypatch.setattr(search, "_pixabay_key", lambda: "test-key")

    with pytest.raises(ValueError, match="interactive confirmation"):
        search.search_recipe(Recipe(7, "Soup", "soup"), tmp_path, force=True, session=session)

    assert session.calls == []


def test_force_refresh_of_expired_cache_does_not_require_recent_confirmation(tmp_path, monkeypatch):
    """Allow forced refresh of an expired entry without treating it as a recent-cache overwrite."""
    _write_cache(tmp_path / "7.json", fetched_at=datetime.now(UTC) - timedelta(hours=25))
    session = FakeSession([FakeResponse({"hits": [_hit(8, "soup")]})])
    monkeypatch.setattr(search, "_pixabay_key", lambda: "test-key")

    hits, cached = search.search_recipe(
        Recipe(7, "Soup", "soup"), tmp_path, force=True, session=session
    )

    assert [hit["id"] for hit in hits] == [8]
    assert cached is False
    assert len(session.calls) == 1


def test_confirmed_force_refresh_ranks_caps_and_replaces_cached_hits(tmp_path, monkeypatch):
    """Refresh an accepted recent cache and rank API hits by their tags.

    Keep only five candidates and verify the replacement cache stores the normalized result.
    """
    cache_file = tmp_path / "7.json"
    _write_cache(cache_file, hits=[_hit(99, "old soup")])
    api_hits = [_hit(6, "bread")] + [_hit(index, "soup tomato") for index in range(1, 6)]
    session = FakeSession([FakeResponse({"hits": api_hits + ["not an object"]})])
    monkeypatch.setattr(search, "_pixabay_key", lambda: "test-key")
    sleeps = []

    hits, cached = search.search_recipe(
        Recipe(7, "Soup", "soup"),
        tmp_path,
        force=True,
        confirm_recent=True,
        session=session,
        sleep=sleeps.append,
    )

    assert [hit["id"] for hit in hits] == [1, 2, 3, 4, 5]
    assert cached is False
    assert len(session.calls) == 1
    url, request = session.calls[0]
    assert url == search.API_URL
    assert request["timeout"] == search.TIMEOUT
    assert request["params"] == {
        "key": "test-key",
        "q": "soup",
        "category": "food",
        "image_type": "photo",
        "per_page": 10,
        "safesearch": "true",
        "min_width": 800,
        "lang": "ko",
    }
    saved = json.loads(cache_file.read_text(encoding="utf-8"))
    assert [hit["id"] for hit in saved["hits"]] == [1, 2, 3, 4, 5]
    assert saved["query"] == "soup"
    assert saved["lang"] == "ko"


def test_search_retries_transient_request_exception(tmp_path, monkeypatch):
    """Retry a timeout once, then return the successful result.

    Injected sleeps capture pacing without making the test wait in real time.
    """
    session = FakeSession(
        [requests.Timeout("temporary"), FakeResponse({"hits": [_hit(1, "soup")]})]
    )
    monkeypatch.setattr(search, "_pixabay_key", lambda: "test-key")
    sleeps = []

    hits, cached = search.search_recipe(
        Recipe(1, "Soup", "soup"), tmp_path, session=session, sleep=sleeps.append
    )

    assert [hit["id"] for hit in hits] == [1]
    assert cached is False
    assert len(session.calls) == 2
    assert sleeps
    assert all(seconds > 0 for seconds in sleeps)


def test_search_waits_for_rate_limit_reset_and_low_remaining_quota(tmp_path, monkeypatch):
    """Honor reset delays after a 429 and when the successful response leaves little quota.

    The fake sleep collector confirms both server-provided reset values are used.
    """
    session = FakeSession(
        [
            FakeResponse(status_code=429, headers={"X-RateLimit-Reset": "7"}),
            FakeResponse(
                {"hits": [_hit(1, "soup")]},
                headers={"X-RateLimit-Reset": "11", "X-RateLimit-Remaining": "3"},
            ),
        ]
    )
    monkeypatch.setattr(search, "_pixabay_key", lambda: "test-key")
    sleeps = []

    hits, _cached = search.search_recipe(
        Recipe(1, "Soup", "soup"), tmp_path, session=session, sleep=sleeps.append
    )

    assert [hit["id"] for hit in hits] == [1]
    assert len(session.calls) == 2
    assert 7 in sleeps
    assert 11 in sleeps


def test_search_reports_failure_after_three_request_errors(tmp_path, monkeypatch):
    """Stop after the configured three attempts and expose the failure as RuntimeError."""
    session = FakeSession([requests.Timeout("offline") for _ in range(3)])
    monkeypatch.setattr(search, "_pixabay_key", lambda: "test-key")

    with pytest.raises(RuntimeError, match="Pixabay request failed"):
        search.search_recipe(
            Recipe(1, "Soup", "soup"), tmp_path, session=session, sleep=lambda _seconds: None
        )

    assert len(session.calls) == 3


def test_search_requires_a_pixabay_key_on_cache_miss(tmp_path, monkeypatch):
    """Fail with a configuration hint before network work when the cache has no result.

    Confirm the injected session receives no call when the API key is absent.
    """
    monkeypatch.setattr(search, "_pixabay_key", lambda: None)
    session = FakeSession([])

    with pytest.raises(ValueError, match="Set PIXABAY_KEY"):
        search.search_recipe(Recipe(1, "Soup", "soup"), tmp_path, session=session)

    assert session.calls == []


def test_final_rate_limit_response_is_reported_after_retry_budget(tmp_path, monkeypatch):
    """Convert a third 429 HTTP error into the search operation's public RuntimeError."""
    session = FakeSession([FakeResponse(status_code=429) for _ in range(3)])
    monkeypatch.setattr(search, "_pixabay_key", lambda: "test-key")

    with pytest.raises(RuntimeError, match="Pixabay request failed"):
        search.search_recipe(
            Recipe(1, "Soup", "soup"), tmp_path, session=session, sleep=lambda _seconds: None
        )

    assert len(session.calls) == 3
