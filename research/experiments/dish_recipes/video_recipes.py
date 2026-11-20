# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
# ruff: noqa: E501
"""Structured recipes written by a Gemini model that watches the public YouTube video itself.

The request is an OpenRouter chat completion with a ``video_url`` part holding the YouTube link;
OpenRouter forwards YouTube links only to Google AI Studio, so the provider is pinned there. The
model first says whether the video cooks the requested dish, then writes the recipe in its own
words. ``to_recipe`` turns the answer into the stored recipe format (``schema.json``,
``source = "ai_structured_from_video"``); answers for another dish yield ``None``.
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

import httpx

from .common import read_key

URL = "https://openrouter.ai/api/v1/chat/completions"
PROVIDER = {"only": ["google-ai-studio"], "allow_fallbacks": False}
RETRY_WAITS_S = (3.0, 8.0)  # the server's retry pause for HTTP 429
VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")

SYSTEM = """You watch a Korean cooking video and write the recipe it shows, for a student cooking alone.

1. First decide whether the video's main content is cooking the requested dish (popular variants count; a different dish, a vlog, a mukbang, an advertisement or a compilation does not). Put the dish the video actually cooks in cooked_dish.
2. Write what the video shows or says, in your own words, in Korean. Do not add ingredients, amounts or steps from general cooking knowledge. Use "" for an amount that is neither said nor shown, and 0 for unknown servings.
3. For every ingredient give evidence: "heard" (said or on-screen text), "seen" (only visible) or "both". List anything you are unsure about in uncertain.
4. role: main = what the dish is named after or built on, secondary = other food, seasoning = sauces, oil, salt, sugar, spices. Names are plain common Korean names without brands.
5. Steps are short imperative sentences, at most 200 characters each, in cooking order."""

ANSWER_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "is_requested_dish",
        "cooked_dish",
        "servings",
        "ingredients",
        "steps",
        "tips",
        "uncertain",
    ],
    "properties": {
        "is_requested_dish": {"type": "boolean"},
        "cooked_dish": {"type": "string"},
        "servings": {"type": "integer"},
        "ingredients": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["name", "amount", "role", "evidence"],
                "properties": {
                    "name": {"type": "string"},
                    "amount": {"type": "string"},
                    "role": {"type": "string", "enum": ["main", "secondary", "seasoning"]},
                    "evidence": {"type": "string", "enum": ["heard", "seen", "both"]},
                },
            },
        },
        "steps": {"type": "array", "items": {"type": "string"}},
        "tips": {"type": "array", "items": {"type": "string"}},
        "uncertain": {"type": "array", "items": {"type": "string"}},
    },
}


@dataclass
class Call:
    ok: bool
    answer: dict | None = None
    error: str = ""
    finish_reason: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    latency_s: float = 0.0
    attempts: int = 0
    provider: str = ""
    extra: dict = field(default_factory=dict)


def watch_url(video_id: str) -> str:
    if not VIDEO_ID.match(video_id):
        raise ValueError(f"not a YouTube video id: {video_id!r}")
    return f"https://www.youtube.com/watch?v={video_id}"


def build_payload(dish_name: str, video_id: str, model: str) -> dict:
    return {
        "model": model,
        "temperature": 0,
        "max_tokens": 4096,
        "provider": PROVIDER,
        "usage": {"include": True},
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "video_recipe", "strict": True, "schema": ANSWER_SCHEMA},
        },
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": f"Requested dish: {dish_name}"},
                    {"type": "video_url", "video_url": {"url": watch_url(video_id)}},
                ],
            },
        ],
    }


def call(payload: dict, client: httpx.Client | None = None, timeout_s: float = 180.0) -> Call:
    """One request with the server's 429 retries; never raises for provider or format errors."""
    key = read_key("OPENROUTER_API_KEY", "openrouter.env")
    if not key:
        return Call(ok=False, error="no OpenRouter key")
    own = client is None
    client = client or httpx.Client(timeout=timeout_s)
    started, attempts = time.monotonic(), 0
    try:
        for wait in (*RETRY_WAITS_S, None):
            attempts += 1
            response = client.post(URL, json=payload, headers={"Authorization": f"Bearer {key}"})
            if response.status_code == 429 and wait is not None:
                time.sleep(wait)
                continue
            break
        latency = time.monotonic() - started
        if response.status_code != 200:
            return Call(
                ok=False,
                error=f"HTTP {response.status_code}: {response.text[:200]}",
                latency_s=latency,
                attempts=attempts,
            )
        return parse_response(response.json(), latency, attempts)
    except httpx.HTTPError as exc:
        return Call(ok=False, error=type(exc).__name__, attempts=attempts)
    finally:
        if own:
            client.close()


def parse_response(body: dict, latency_s: float = 0.0, attempts: int = 1) -> Call:
    usage = body.get("usage") or {}
    choice = (body.get("choices") or [{}])[0]
    out = Call(
        ok=False,
        finish_reason=str(choice.get("finish_reason") or ""),
        prompt_tokens=int(usage.get("prompt_tokens") or 0),
        completion_tokens=int(usage.get("completion_tokens") or 0),
        cost_usd=float(usage.get("cost") or 0.0),
        latency_s=latency_s,
        attempts=attempts,
        provider=str(body.get("provider") or ""),
    )
    if "error" in body:
        out.error = str(body["error"])[:200]
        return out
    text = (choice.get("message") or {}).get("content") or ""
    try:
        answer = json.loads(text)
    except json.JSONDecodeError:
        out.error = "answer is not JSON"
        return out
    if not isinstance(answer, dict):
        out.error = "answer is not an object"
        return out
    out.ok, out.answer = True, answer
    return out


def to_recipe(dish_id: str, video: dict, answer: dict, generated_at: str | None = None):
    """The stored recipe for this dish, or None when the video cooks another dish."""
    if not answer.get("is_requested_dish"):
        return None
    steps = [s.strip() for s in answer.get("steps", []) if s and s.strip()]
    ingredients = [
        {
            "name": i["name"].strip(),
            "amount": i["amount"].strip() or None,
            "role": i["role"],
        }
        for i in answer.get("ingredients", [])
        if i.get("name", "").strip()
    ]
    servings = answer.get("servings") or None
    return {
        "dish_id": dish_id,
        "video": {
            "id": video["id"],
            "title": video.get("title", ""),
            "channel": video.get("channel", ""),
        },
        "source": "ai_structured_from_video",
        "generated_at": generated_at or datetime.now(UTC).replace(microsecond=0).isoformat(),
        "servings": servings if isinstance(servings, int) and servings > 0 else None,
        "ingredients": ingredients,
        "steps": [{"n": n, "text": text} for n, text in enumerate(steps, start=1)],
        "tips": [t.strip() for t in answer.get("tips", []) if t and t.strip()],
        "uncertain": [u.strip() for u in answer.get("uncertain", []) if u and u.strip()],
        "caption_gaps": False,
    }


def evidence(answer: dict) -> dict[str, str]:
    """Ingredient name -> heard / seen / both, as the model reported it."""
    return {i["name"].strip(): i.get("evidence", "") for i in answer.get("ingredients", [])}
