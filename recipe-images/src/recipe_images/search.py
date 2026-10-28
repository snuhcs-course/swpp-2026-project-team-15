"""Pixabay search with a 24-hour cache and conservative request pacing."""
from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import requests

from .models import Recipe, hit_fields

API_URL = "https://pixabay.com/api/"
TIMEOUT = 10

def read_cache(path: Path, query: str, now: datetime | None = None) -> list[dict[str, Any]] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(payload["fetched_at"])
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=UTC)
        current = now or datetime.now(UTC)
        if payload.get("query") == query and timedelta(0) <= current - fetched < timedelta(hours=24):
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

def search_recipe(recipe: Recipe, cache_dir: Path, force: bool = False, confirm_recent: bool = False,
                  session: requests.Session | None = None, sleep=time.sleep) -> tuple[list[dict[str, Any]], bool]:
    cache_path = cache_dir / f"{recipe.id}.json"
    cached = read_cache(cache_path, recipe.query)
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
            raise ValueError("Recent cache exists; interactive confirmation is required to force refresh")
    key = os.environ.get("PIXABAY_KEY")
    if not key:
        raise ValueError("PIXABAY_KEY environment variable is required")
    client = session or requests.Session()
    params = {"key": key, "q": recipe.query, "category": "food", "image_type": "photo",
              "per_page": 5, "safesearch": "true", "min_width": 800, "lang": "en"}
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
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps({"fetched_at": datetime.now(UTC).isoformat(),
                "query": recipe.query, "hits": hits}, ensure_ascii=False, indent=2), encoding="utf-8")
            remaining = response.headers.get("X-RateLimit-Remaining")
            if remaining and remaining.isdigit() and int(remaining) <= 5:
                _wait_reset(response, sleep)
            return hits, False
        except requests.RequestException as exc:
            last_error = exc
            if attempt < 2:
                sleep(min(2 ** attempt, 4))
    raise RuntimeError(f"Pixabay request failed: {last_error}")
