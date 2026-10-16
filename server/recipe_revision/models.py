"""Immutable source records independent of persistence and web frameworks."""
# AI-generated initial importer with Codex (GPT-6.1 Sol)
# 2026-10-14 to 2026-10-26; reviewed by Soohyun An

from dataclasses import dataclass


@dataclass(frozen=True)
class InventoryIngredient:
    """An available normalized ingredient; no quantity sufficiency is implied."""

    ingredient_id: int
    name: str


@dataclass(frozen=True)
class SourceIngredient:
    """One original relationship row, including repeated normalized IDs."""

    recipe_ingredient_id: int
    ingredient_id: int
    name: str
    quantity_text: str | None
    ingredient_type_code: str
    ingredient_type: str | None
    original_name: str | None


@dataclass(frozen=True)
class SourceStep:
    """An original step with its stable source identity and nullable context."""

    step_id: int
    step_number: int
    instruction: str
    image_url: str | None
    tip: str | None


@dataclass(frozen=True)
class SourceRecipe:
    """Full original recipe snapshot; quantities and servings stay as text."""

    recipe_id: int
    name: str
    description: str | None
    cuisine_type: str | None
    category: str | None
    cooking_time: str | None
    calories: str | None
    servings: str | None
    difficulty: str | None
    main_image_url: str | None
    source_url: str | None
    ingredients: tuple[SourceIngredient, ...]
    steps: tuple[SourceStep, ...]

    def __post_init__(self) -> None:
        # Copy sequences so callers cannot mutate original rows through a list.
        object.__setattr__(self, "ingredients", tuple(self.ingredients))
        object.__setattr__(self, "steps", tuple(self.steps))
