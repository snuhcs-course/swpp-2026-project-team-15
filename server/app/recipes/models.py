# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.

# Modified with Codex (GPT-6.1 Sol), 2026-10-17; reviewed by Soohyun An.
# Changes: Map existing recipe metadata, ingredient classifications, original names, and step tips.

"""SQLModel tables mirroring server/db/schema.sql, which remains the source of truth.

Only the tables the API reads are mapped; tools and allergens are still empty.
"""

from sqlmodel import Field, SQLModel


class Recipe(SQLModel, table=True):
    __tablename__ = "recipe"

    recipe_id: int = Field(primary_key=True)
    name: str
    description: str | None = None
    cuisine_type: str | None = None
    category: str | None = None
    cooking_time: str | None = None
    calories: str | None = None
    servings: str | None = None
    difficulty: str | None = None


class RecipeStep(SQLModel, table=True):
    __tablename__ = "recipe_step"

    step_id: int = Field(primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.recipe_id")
    step_number: int
    instruction: str
    tip: str | None = None


class Ingredient(SQLModel, table=True):
    __tablename__ = "ingredient"

    ingredient_id: int = Field(primary_key=True)
    name: str = Field(unique=True)


class RecipeIngredient(SQLModel, table=True):
    __tablename__ = "recipe_ingredient"

    recipe_ingredient_id: int = Field(primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.recipe_id")
    ingredient_id: int = Field(foreign_key="ingredient.ingredient_id")
    quantity_text: str | None = None
    ingredient_type_code: str
    ingredient_type: str | None = None
    original_name: str | None = None
