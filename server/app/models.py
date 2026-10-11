# AI-generated with Claude Code (Opus 5.5), 2026-10-11; review pending by Jaehyuk Choi.
"""SQLModel tables mirroring server/db/schema.sql, which remains the source of truth.

Only the tables the API reads are mapped; tools and allergens are still empty.
"""

from sqlmodel import Field, SQLModel


class Recipe(SQLModel, table=True):
    __tablename__ = "recipe"

    recipe_id: int = Field(primary_key=True)
    name: str
    cooking_time: str | None = None
    servings: str | None = None


class RecipeStep(SQLModel, table=True):
    __tablename__ = "recipe_step"

    step_id: int = Field(primary_key=True)
    recipe_id: int = Field(foreign_key="recipe.recipe_id")
    step_number: int
    instruction: str


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
