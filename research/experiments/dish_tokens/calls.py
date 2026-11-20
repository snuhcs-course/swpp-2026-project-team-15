# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""One OpenRouter chat call with usage bookkeeping (token and pipeline studies)."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
KEY_FILE = Path.home() / ".config" / "mylittlechef" / "openrouter.env"
PRICE_PER_MTOK = (0.10, 0.40)  # google/gemini-2.5-flash-lite input/output, USD


def read_key() -> str:
    key = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if not key and KEY_FILE.exists():
        for line in KEY_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith("OPENROUTER_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("\"'")
    return key


@dataclass
class Call:
    ok: bool
    status: int = 0
    latency_s: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0
    finish_reason: str | None = None
    data: dict | None = None
    error: str | None = None
    citations: list[str] = field(default_factory=list)

    @property
    def truncated(self) -> bool:
        return self.finish_reason == "length"


def chat(payload: dict, key: str, timeout: float = 90.0) -> Call:
    """POST one request; never raises. ``data`` is the parsed JSON content when complete."""
    started = time.monotonic()
    try:
        response = httpx.post(
            ENDPOINT,
            json=payload,
            headers={"Authorization": f"Bearer {key}"},
            timeout=timeout,
            follow_redirects=False,
        )
    except httpx.HTTPError as exc:
        return Call(False, latency_s=time.monotonic() - started, error=type(exc).__name__)
    call = Call(response.status_code == 200, response.status_code, time.monotonic() - started)
    try:
        body = response.json()
    except ValueError:
        call.ok, call.error = False, "invalid response body"
        return call
    if response.status_code != 200:
        call.error = str((body.get("error") or {}).get("message", "error"))[:120]
        return call
    usage = body.get("usage") or {}
    call.prompt_tokens = int(usage.get("prompt_tokens") or 0)
    call.completion_tokens = int(usage.get("completion_tokens") or 0)
    call.reasoning_tokens = int(
        (usage.get("completion_tokens_details") or {}).get("reasoning_tokens") or 0
    )
    call.cached_tokens = int((usage.get("prompt_tokens_details") or {}).get("cached_tokens") or 0)
    cost = usage.get("cost")
    call.cost_usd = (
        float(cost)
        if cost is not None
        else (call.prompt_tokens * PRICE_PER_MTOK[0] + call.completion_tokens * PRICE_PER_MTOK[1])
        / 1e6
    )
    choice = (body.get("choices") or [{}])[0]
    call.finish_reason = choice.get("finish_reason")
    message = choice.get("message") or {}
    call.citations = [
        a.get("url_citation", {}).get("url", "") for a in message.get("annotations") or []
    ]
    if call.finish_reason == "length":
        call.ok, call.error = False, "truncated"
        return call
    content = message.get("content") or ""
    try:
        data = json.loads(content)
    except ValueError:  # web-search answers may wrap the JSON in a code fence or prose
        start, end = content.find("{"), content.rfind("}")
        try:
            data = json.loads(content[start : end + 1]) if 0 <= start < end else None
        except ValueError:
            data = None
        if data is None:
            call.ok, call.error = False, "answer is not JSON"
            return call
    if isinstance(data, dict):
        call.data = data
    else:
        call.ok, call.error = False, "answer is not an object"
    return call


def json_schema_format(name: str, schema: dict) -> dict:
    return {"type": "json_schema", "json_schema": {"name": name, "strict": True, "schema": schema}}
