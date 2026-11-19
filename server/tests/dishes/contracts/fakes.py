# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Small hand-written fakes of the roles; each must pass the same contract as the real class."""

from datetime import datetime

from app.dishes.catalog import Dish
from app.dishes.errors import DishLLMError, VideoError
from app.dishes.schemas import SourceRecipe, Video
from app.dishes.video_store import MAX_AGE

ID_A, ID_B = "a" * 11, "b" * 11


class FakeChatModel:
    def __init__(self, answer: dict | None = None, *, fail: bool = False):
        self._answer, self._fail = answer or {"dishes": []}, fail

    def complete(
        self, system: str, user: str, name: str, schema: dict, max_tokens: int | None = None
    ) -> dict:
        if self._fail:
            raise DishLLMError("down")
        return self._answer


class FakeVideoSource:
    def __init__(self, ids: list[str], *, fail: bool = False):
        self._ids, self._fail = ids, fail

    def propose(self, dish_name: str) -> list[str]:
        if self._fail:
            raise VideoError("down")
        return list(dict.fromkeys(self._ids))


class FakeVideoVerifier:
    def __init__(self, usable: set[str], *, fail: bool = False):
        self._usable, self._fail = usable, fail

    def check(self, ids: list[str]) -> list[Video]:
        if self._fail:
            raise VideoError("down")
        return [
            Video(video_id=i, title="t", channel="c", thumbnail_url="u")
            for i in ids
            if i in self._usable
        ]


class FakeStoredVideos:
    def __init__(self, entries: dict[str, tuple[datetime, list[str]]]):
        self._entries = entries

    def fresh_ids(self, dish_id: str, now: datetime) -> list[str]:
        entry = self._entries.get(dish_id)
        return entry[1] if entry and now - entry[0] < MAX_AGE else []


class FakeRecipeBook:
    def __init__(self, recipes: dict[str, SourceRecipe]):
        self._recipes = recipes

    def get(self, dish_id: str) -> SourceRecipe | None:
        return self._recipes.get(dish_id)

    def __contains__(self, dish_id: str) -> bool:
        return dish_id in self._recipes


class FakeCatalog:
    def __init__(self, dishes: list[Dish]):
        self._dishes = dishes

    def get(self, dish_id: str) -> Dish | None:
        return next((d for d in self._dishes if d.id == dish_id), None)

    def by_name(self, name: str) -> Dish | None:
        return next((d for d in self._dishes if d.name == name), None)

    def all(self) -> list[Dish]:
        return list(self._dishes)

    def __len__(self) -> int:
        return len(self._dishes)


class FakeIngredientIndex:
    NAMES = ["계란", "김치", "밥"]

    def owned(self, ingredients: list[str]) -> set[str]:
        return {i.strip() for i in ingredients if i.strip()}

    def status(self, name: str, owned: set[str]) -> str:
        return "owned" if name in owned else "unavailable"

    def ingredient_names(self) -> list[str]:
        return list(self.NAMES)

    def additions(self, ingredients: list[str], limit: int = 5) -> list[dict]:
        return [{"name": n} for n in self.NAMES if n not in ingredients][:limit]
