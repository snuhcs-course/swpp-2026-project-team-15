# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Offline tests of the token-study payloads, the decision helper and the call bookkeeping."""

import json

import httpx
import pytest
from experiments.dish_tokens import calls
from experiments.dish_tokens.run_tokens import CEILING, main, payload_for, qualifies, user_message

NAMES = ["김치죽", "계란말이"]


def test_variants_change_only_what_they_claim():
    base = payload_for("B", ["김치"], NAMES)
    assert base["max_tokens"] == CEILING and "reasoning" not in base
    assert payload_for("V0", ["김치"], NAMES)["max_tokens"] == 2048
    assert payload_for("V1a", ["김치"], NAMES)["max_tokens"] == 1024
    assert payload_for("V3", ["김치"], NAMES)["reasoning"] == {"enabled": False}
    schema = payload_for("V4", ["김치"], NAMES)["response_format"]["json_schema"]["schema"]
    item = schema["properties"]["dishes"]["items"]
    assert set(item["properties"]) == {"name", "missing"} and item["required"] == ["name", "missing"]
    assert "have" in base["response_format"]["json_schema"]["schema"]["properties"]["dishes"]["items"]["properties"]


def test_message_layouts():
    assert user_message("V2", ["김치", "밥"], NAMES) == "owned: 김치, 밥\ndishes: 김치죽, 계란말이"
    assert list(json.loads(user_message("B", ["김치"], NAMES))) == ["owned", "dishes"]
    assert list(json.loads(user_message("V5", ["김치"], NAMES))) == ["dishes", "owned"]


def test_qualification_needs_no_truncation_and_two_points():
    base = {"have_subset_share": 0.95, "reference_recall": 0.5}
    assert qualifies({"have_subset_share": 0.94, "reference_recall": 0.49}, base, 0)
    assert not qualifies({"have_subset_share": 0.92, "reference_recall": 0.5}, base, 0)
    assert not qualifies(base, base, 1)
    assert qualifies({"have_subset_share": 0.1, "reference_recall": 0.5}, base, 0, ("have_subset_share",))


def test_chat_reads_usage_and_flags_truncation(monkeypatch):
    def fake_post(url, json, headers, timeout, follow_redirects):  # noqa: A002
        body = {
            "choices": [{"finish_reason": "stop", "message": {"content": '{"dishes": []}'}}],
            "usage": {
                "prompt_tokens": 10, "completion_tokens": 4, "cost": 0.5,
                "completion_tokens_details": {"reasoning_tokens": 2},
                "prompt_tokens_details": {"cached_tokens": 6},
            },
        }
        return httpx.Response(200, json=body)

    monkeypatch.setattr(calls.httpx, "post", fake_post)
    call = calls.chat({"x": 1}, "key")
    assert call.ok and call.data == {"dishes": []} and call.cost_usd == 0.5
    assert (call.prompt_tokens, call.completion_tokens, call.reasoning_tokens, call.cached_tokens) == (10, 4, 2, 6)

    def cut(url, json, headers, timeout, follow_redirects):  # noqa: A002
        return httpx.Response(200, json={"choices": [{"finish_reason": "length", "message": {"content": "{"}}], "usage": {}})

    monkeypatch.setattr(calls.httpx, "post", cut)
    assert calls.chat({}, "k").truncated

    def boom(*a, **k):
        raise httpx.ConnectError("x")

    monkeypatch.setattr(calls.httpx, "post", boom)
    assert not calls.chat({}, "k").ok


def test_dry_run_makes_no_call(capsys):
    assert main([]) == 0
    assert "12 inputs x 8 variants = 96 calls" in capsys.readouterr().out
