"""Shared data models and validated recipe input loading."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Recipe:
    id: int
    name_ko: str
    query: str

@dataclass(frozen=True)
class Selection:
    recipe_id: int
    pixabay_id: int
    user: str
    user_id: int
    page_url: str
    tags: str

def load_recipes(path: Path) -> list[Recipe]:
    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Unable to read recipes file {path}: {exc}") from exc
    if not isinstance(raw, list):
        raise ValueError("recipes.json must contain a JSON array")
    recipes: list[Recipe] = []
    seen: set[int] = set()
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Recipe #{index} must be a JSON object")
        recipe_id, name, query = item.get("id"), item.get("name_ko"), item.get("query")
        if isinstance(recipe_id, bool) or not isinstance(recipe_id, int):
            raise ValueError(f"Recipe #{index}: id must be an integer")
        if recipe_id in seen:
            raise ValueError(f"Recipe #{index}: duplicate id {recipe_id}")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Recipe #{index}: name_ko must be a non-empty string")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"Recipe #{index}: query is required")
        if len(query) > 100:
            raise ValueError(f"Recipe #{index}: query must be 100 characters or fewer")
        seen.add(recipe_id)
        recipes.append(Recipe(recipe_id, name.strip(), query.strip()))
    return recipes

def hit_fields(hit: dict[str, Any]) -> dict[str, Any]:
    names = ("id", "pageURL", "webformatURL", "tags", "user", "user_id", "imageWidth", "imageHeight")
    return {name: hit.get(name, "") for name in names}
