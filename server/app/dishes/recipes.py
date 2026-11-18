# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
"""Structured recipes of the dishes, one per dish, read once from a JSON file."""

import json
from pathlib import Path

from pydantic import ValidationError

from app.dishes.schemas import SourceRecipe

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

    def __contains__(self, dish_id: str) -> bool:
        return dish_id in self._recipes

    def __len__(self) -> int:
        return len(self._recipes)
