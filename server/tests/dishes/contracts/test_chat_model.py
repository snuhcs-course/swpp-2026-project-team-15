# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Every ChatModel returns a JSON object or raises DishLLMError, never anything else."""

import httpx
import pytest

from app.dishes.errors import DishLLMError
from app.dishes.llm import DishLLM
from tests.dishes.contracts.fakes import FakeChatModel

SCHEMA = {"type": "object"}


class ChatModelContract:
    def make(self, *, fail: bool):
        raise NotImplementedError

    def test_returns_a_json_object(self):
        answer = self.make(fail=False).complete("system", "{}", "name", SCHEMA)
        assert isinstance(answer, dict)

    def test_a_failed_call_is_a_dish_llm_error(self):
        with pytest.raises(DishLLMError):
            self.make(fail=True).complete("system", "{}", "name", SCHEMA)


class TestFakeChatModel(ChatModelContract):
    def make(self, *, fail):
        return FakeChatModel({"dishes": []}, fail=fail)


class TestDishLLM(ChatModelContract):
    def make(self, *, fail):
        def handler(request):
            if fail:
                return httpx.Response(500)
            body = {
                "choices": [{"finish_reason": "stop", "message": {"content": '{"dishes": []}'}}]
            }
            return httpx.Response(200, json=body)

        return DishLLM("key", transport=httpx.MockTransport(handler))
