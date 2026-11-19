# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
"""Structured recipes of the dishes, one per dish, read once from a JSON file.

``CreditedRecipes`` wraps a recipe book and fills in the title and channel of each recipe's video
from a live YouTube lookup, so the recipe file needs to keep only the video id (YouTube API data
such as titles may not be stored longer than 30 days).
"""

import json
import time
from collections.abc import Callable
from pathlib import Path

from pydantic import ValidationError

from app.dishes.errors import VideoError
from app.dishes.roles import RecipeBook, VideoVerifier
from app.dishes.schemas import RecipeVideo, SourceRecipe

CREDIT_SECONDS = 24 * 3600  # how long a looked-up title and channel are reused

SCHEMA = 1


class RecipeStore:
    def __init__(self, recipes: dict[str, SourceRecipe] | None = None):
        self._recipes = recipes or {}

    @classmethod
    def load(cls, path: Path | str | None) -> "RecipeStore":
        """An empty store without a path; a path that cannot be read or parsed is an error."""
        if not path:
            return cls()
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("schema") != SCHEMA or not isinstance(data.get("recipes"), dict):
            raise ValueError("recipe file: expected {'schema': 1, 'recipes': {...}}")
        recipes: dict[str, SourceRecipe] = {}
        for dish_id, raw in data["recipes"].items():
            try:
                recipe = SourceRecipe.model_validate(raw)
            except ValidationError as exc:
                raise ValueError(f"recipe file: invalid recipe for {dish_id}") from exc
            if recipe.dish_id != dish_id:
                raise ValueError(f"recipe file: key {dish_id} does not match dish_id")
            recipes[dish_id] = recipe
        return cls(recipes)

    def get(self, dish_id: str) -> SourceRecipe | None:
        return self._recipes.get(dish_id)

    def video_id(self, dish_id: str) -> str | None:
        recipe = self._recipes.get(dish_id)
        return recipe.video.id if recipe is not None and recipe.video is not None else None

    def __contains__(self, dish_id: str) -> bool:
        return dish_id in self._recipes

    def __len__(self) -> int:
        return len(self._recipes)


class CreditedRecipes:
    """A recipe book whose video credit (title, channel) comes from YouTube, not from the file.

    A video that no longer exists or cannot be embedded, or a failed lookup, leaves the credit
    empty; the recipe itself is still served.
    """

    def __init__(
        self,
        recipes: RecipeBook,
        verifier: VideoVerifier,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._recipes, self._verifier, self._clock = recipes, verifier, clock
        self._credits: dict[str, tuple[float, str, str]] = {}

    def get(self, dish_id: str) -> SourceRecipe | None:
        recipe = self._recipes.get(dish_id)
        if recipe is None or recipe.video is None:
            return recipe
        title, channel = self._credit(recipe.video.id)
        video = RecipeVideo(id=recipe.video.id, title=title, channel=channel)
        return recipe.model_copy(update={"video": video})

    def video_id(self, dish_id: str) -> str | None:
        return self._recipes.video_id(dish_id)

    def __contains__(self, dish_id: str) -> bool:
        return dish_id in self._recipes

    def _credit(self, video_id: str) -> tuple[str, str]:
        cached = self._credits.get(video_id)
        if cached and self._clock() - cached[0] < CREDIT_SECONDS:
            return cached[1], cached[2]
        try:
            found = self._verifier.check([video_id])
        except VideoError:
            return "", ""  # not cached: the next request tries again
        title, channel = (found[0].title, found[0].channel) if found else ("", "")
        self._credits[video_id] = (self._clock(), title, channel)
        return title, channel
