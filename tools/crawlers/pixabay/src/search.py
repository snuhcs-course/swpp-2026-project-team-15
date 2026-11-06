# AI-generated initial implementation with Codex (GPT-6 Luna Medium),
# 2026-11-03; reviewed by Ahyoon Choi.

"""Pixabay search with a 24-hour cache and conservative request pacing."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from config import load_config
from models import Recipe, hit_fields

API_URL = "https://pixabay.com/api/"
TIMEOUT = 10
SEARCH_LANGUAGE = "ko"


def _pixabay_key() -> str | None:
    """Read PIXABAY_KEY from the process environment or tools/.env."""
    return load_config().pixabay_key


def read_cache(
    path: Path, query: str, now: datetime | None = None, lang: str = SEARCH_LANGUAGE
) -> list[dict[str, Any]] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(payload["fetched_at"])
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=UTC)
        current = now or datetime.now(UTC)
        if (
            payload.get("query") == query
            and payload.get("lang") == lang
            and timedelta(0) <= current - fetched < timedelta(hours=24)
        ):
            hits = payload.get("hits")
            return hits if isinstance(hits, list) else None
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
    return None


def _wait_reset(response: requests.Response, sleep=time.sleep) -> None:
    try:
        seconds = max(0, int(response.headers.get("X-RateLimit-Reset", "0")))
    except ValueError:
        seconds = 0
    if seconds:
        sleep(seconds)


def _tag_match_score(query: str, tags: str) -> int:
    normalized_query = "".join(character for character in query.casefold() if character.isalnum())
    normalized_tags = "".join(character for character in tags.casefold() if character.isalnum())
    if not normalized_query:
        return 0
    if len(normalized_query) == 1:
        return int(normalized_query in normalized_tags)
    query_bigrams = {
        normalized_query[index : index + 2] for index in range(len(normalized_query) - 1)
    }
    return sum(bigram in normalized_tags for bigram in query_bigrams)


def search_recipe(
    recipe: Recipe,
    cache_dir: Path,
    force: bool = False,
    confirm_recent: bool = False,
    session: requests.Session | None = None,
    sleep=time.sleep,
) -> tuple[list[dict[str, Any]], bool]:
    cache_path = cache_dir / f"{recipe.id}.json"
    cached = read_cache(cache_path, recipe.query, lang=SEARCH_LANGUAGE)
    if cached is not None and not force:
        return cached, True
    if force and cache_path.exists():
        try:
            previous = json.loads(cache_path.read_text(encoding="utf-8"))
            fetched = datetime.fromisoformat(previous["fetched_at"])
            if fetched.tzinfo is None:
                fetched = fetched.replace(tzinfo=UTC)
            recent = datetime.now(UTC) - fetched < timedelta(hours=24)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            recent = False
        if recent and not confirm_recent:
            raise ValueError(
                "Recent cache exists; interactive confirmation is required to force refresh"
            )
    key = _pixabay_key() # pixabay api key
    if not key:
        raise ValueError("Set PIXABAY_KEY in tools/.env or the process environment")
    client = session or requests.Session()
    params = {
        "key": key,
        "q": recipe.query,
        "category": "food",
        "image_type": "photo",
        "per_page": 10,
        "safesearch": "true",
        "min_width": 800,
        "lang": SEARCH_LANGUAGE,
    }
    last_error: Exception | None = None
    last_request = 0.0
    for attempt in range(3):
        try:
            elapsed = time.monotonic() - last_request
            if last_request and elapsed < 1:
                sleep(1 - elapsed)
            last_request = time.monotonic()
            response = client.get(API_URL, params=params, timeout=TIMEOUT)
            if response.status_code == 429:
                if attempt == 2:
                    response.raise_for_status()
                _wait_reset(response, sleep)
                continue
            response.raise_for_status()
            payload = response.json()
            hits = [hit_fields(hit) for hit in payload.get("hits", []) if isinstance(hit, dict)]
            hits.sort(
                key=lambda hit: _tag_match_score(recipe.query, str(hit.get("tags", ""))),
                reverse=True,
            )
            hits = hits[:5]
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(
                    {
                        "fetched_at": datetime.now(UTC).isoformat(),
                        "query": recipe.query,
                        "lang": SEARCH_LANGUAGE,
                        "hits": hits,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining and remaining.isdigit() and int(remaining) <= 5:
                _wait_reset(response, sleep)
            return hits, False
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 2:
                sleep(min(2**attempt, 4))
    raise RuntimeError(f"Pixabay request failed: {last_error}")
