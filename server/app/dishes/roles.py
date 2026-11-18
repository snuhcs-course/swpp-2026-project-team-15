# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""The roles the dish services depend on. Each is small: a service asks only for what it uses.

The concrete classes are created in one place (dependencies.py) and passed in, so a test can hand
in a fake. ``tests/dishes/contracts`` holds one contract test per role that every implementation
must pass.
"""

from datetime import datetime
from typing import Protocol

from app.dishes.schemas import SourceRecipe, Video


class ChatModel(Protocol):
    def complete(self, system: str, user: str, name: str, schema: dict) -> dict:
        """The model's answer to ``user`` as a JSON object that follows ``schema``.

        Raises DishLLMError when the call fails or the answer is unusable."""
        ...


class VideoSource(Protocol):
    def propose(self, dish_name: str) -> list[str]:
        """YouTube video ids that may show how to cook the dish; may be empty or wrong.

        Raises VideoError when the call fails."""
        ...


class VideoVerifier(Protocol):
    def check(self, ids: list[str]) -> list[Video]:
        """The videos among ``ids`` that exist, are public and can be embedded, in ``ids`` order.

        Raises VideoError when the call fails."""
        ...


class StoredVideos(Protocol):
    def fresh_ids(self, dish_id: str, now: datetime) -> list[str]:
        """The stored video ids of the dish in stored order; empty when none or too old."""
        ...


class RecipeBook(Protocol):
    def get(self, dish_id: str) -> SourceRecipe | None: ...

    def __contains__(self, dish_id: str) -> bool: ...
