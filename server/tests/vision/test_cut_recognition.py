# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""A recognition answer cut at the token limit (research/experiments/recheck_leftovers, item 2)."""

import json

import httpx
import pytest

from app.vision.exceptions import VisionError
from app.vision.openrouter import OpenRouterVisionProvider

ITEM = {"name_raw": "yogurt", "category": "요거트", "confidence": 0.9}


def provider(content: str, finish: str) -> OpenRouterVisionProvider:
    body = {"choices": [{"finish_reason": finish, "message": {"content": content}}]}
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    return OpenRouterVisionProvider("key", "model", transport=transport)


def test_items_finished_before_a_loop_to_the_limit_are_kept():
    # A web fridge photo: the model looped on label text ("Ch\t\t\t...") until max_tokens.
    cut = '{\n  "items": [\n    ' + json.dumps(ITEM) + ',\n    {"name_raw": "Ch' + "\\t" * 50
    items = provider(cut, "length").detect(b"x", "image/jpeg")
    assert [i.category for i in items] == ["요거트"]


def test_a_cut_answer_with_no_finished_item_is_still_an_error():
    with pytest.raises(VisionError):
        provider('{"items": [{"name_raw": "Ch' + "\\t" * 50, "length").detect(b"x", "image/jpeg")
