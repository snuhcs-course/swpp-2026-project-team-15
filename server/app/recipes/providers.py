"""Server-owned Revision providers, independent of experimental case catalogs."""

import json
from collections.abc import Callable

from app.config import Settings
from recipe_revision.adapters import ChatCompletionsLLM
from recipe_revision.core import LLM, LLMResponse, RevisionRequest


class MockRevisionLLM:
    """Return a labeled canned refusal, not a verified feasibility assessment."""

    def generate(self, request: RevisionRequest) -> LLMResponse:
        return LLMResponse(
            json.dumps(
                {
                    "result": {
                        "can_revise": False,
                        "reason": "MOCK ONLY: canned refusal; no AI judgment was made.",
                        "changes": [],
                        "revised_recipe": None,
                    }
                }
            )
        )


def revision_factory(settings: Settings) -> Callable[[], LLM]:
    """Defer validation and live adapter construction until candidates are known."""

    def build() -> LLM:
        if settings.revision_provider == "mock":
            return MockRevisionLLM()
        if settings.revision_provider != "live":
            raise ValueError("Unsupported Revision provider")
        return ChatCompletionsLLM(
            settings.revision_llm_endpoint,
            settings.revision_llm_model,
            settings.revision_llm_api_key,
            max_completion_tokens=4096,
        )

    return build
