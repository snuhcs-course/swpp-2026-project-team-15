# AI-generated initial implementation with Codex (GPT-6), 2026-11-06; reviewed by Ahyoon Choi.

"""Tests for the Pixabay search cache validity rules and malformed-cache handling."""

import json
from datetime import UTC, datetime, timedelta

import pytest
from search import read_cache


def _cache_payload(fetched_at, *, query="soup", lang="ko", hits=None):
    """Create a minimal cache record with overridable fields for focused validity tests."""
    return {
        "fetched_at": fetched_at.isoformat(),
        "query": query,
        "lang": lang,
        "hits": [] if hits is None else hits,
    }


def test_cache_is_valid_just_before_24_hours_but_expires_at_boundary(tmp_path):
    """Check the strict 24-hour TTL boundary and use an injected clock for determinism."""
    now = datetime(2026, 11, 6, 12, tzinfo=UTC)
    cache_file = tmp_path / "1.json"
    cache_file.write_text(
        json.dumps(_cache_payload(now - timedelta(hours=24), hits=[])), encoding="utf-8"
    )

    assert read_cache(cache_file, "soup", now) is None

    cache_file.write_text(
        json.dumps(_cache_payload(now - timedelta(hours=23, minutes=59), hits=[])),
        encoding="utf-8",
    )
    assert read_cache(cache_file, "soup", now) == []


def test_cache_requires_matching_query_and_language(tmp_path):
    """Treat recent results as misses whenever the query text or search language differs."""
    now = datetime(2026, 11, 6, 12, tzinfo=UTC)
    cache_file = tmp_path / "1.json"
    cache_file.write_text(json.dumps(_cache_payload(now - timedelta(minutes=5))), encoding="utf-8")

    assert read_cache(cache_file, "stew", now) is None
    assert read_cache(cache_file, "soup", now, lang="en") is None


@pytest.mark.parametrize(
    "contents",
    [
        "not json",
        "[]",
        "{}",
        '{"fetched_at":"not-a-timestamp","query":"soup","lang":"ko","hits":[]}',
        '{"fetched_at":"2026-11-06T11:00:00+00:00","query":"soup","lang":"ko","hits":{}}',
    ],
)
def test_malformed_cache_files_are_misses(tmp_path, contents):
    """Return a cache miss for invalid JSON, missing fields, timestamps, or non-list hits."""
    cache_file = tmp_path / "bad.json"
    cache_file.write_text(contents, encoding="utf-8")

    assert read_cache(cache_file, "soup") is None


def test_cache_from_the_future_is_not_reused(tmp_path):
    """Reject timestamps later than the caller's current time instead of treating them as fresh."""
    now = datetime(2026, 11, 6, 12, tzinfo=UTC)
    cache_file = tmp_path / "future.json"
    cache_file.write_text(json.dumps(_cache_payload(now + timedelta(seconds=1))), encoding="utf-8")

    assert read_cache(cache_file, "soup", now) is None


def test_missing_cache_file_is_a_miss(tmp_path):
    """Treat recipes that have never been searched as ordinary misses without raising errors."""
    assert read_cache(tmp_path / "missing.json", "soup") is None
