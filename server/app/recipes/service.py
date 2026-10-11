# AI-generated with Claude Code (Opus 5.5), 2026-10-11; review pending by Jaehyuk Choi.
"""Read-only recipe queries over the database built by server/db/import_recipes.py."""

import re

from sqlalchemy import Engine, case, func
from sqlmodel import Session, col, select

from app.recipes.constants import STAPLE_SEASONINGS, with_synonyms
from app.recipes.models import Ingredient, Recipe, RecipeIngredient, RecipeStep
from app.recipes.schemas import RecipeRecommendation

_LEADING_NUMBER = re.compile(r"\d+")


def _leading_int(text: str | None) -> int | None:
    match = _LEADING_NUMBER.match(text or "")
    return int(match.group()) if match else None


class RecipeRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def recommend(
        self, fridge: list[str], max_missing: int, limit: int
    ) -> list[RecipeRecommendation]:
        fridge_names = with_synonyms(fridge) - set(STAPLE_SEASONINGS)
        available_names = fridge_names | set(STAPLE_SEASONINGS)

        fridge_ids = select(Ingredient.ingredient_id).where(col(Ingredient.name).in_(fridge_names))
        available_ids = select(Ingredient.ingredient_id).where(
            col(Ingredient.name).in_(available_names)
        )
        needs = (
            select(RecipeIngredient.recipe_id, RecipeIngredient.ingredient_id).distinct().subquery()
        )
        missing_count = func.sum(case((needs.c.ingredient_id.not_in(available_ids), 1), else_=0))
        fridge_count = func.sum(case((needs.c.ingredient_id.in_(fridge_ids), 1), else_=0))
        # Staples alone do not make a meal, so at least one fridge ingredient must be used.
        ranked = (
            select(needs.c.recipe_id)
            .group_by(needs.c.recipe_id)
            .having(fridge_count >= 1, missing_count <= max_missing)
            .order_by(missing_count, fridge_count.desc(), needs.c.recipe_id)
            .limit(limit)
        )

        with Session(self._engine) as session:
            recipe_ids = session.exec(ranked).all()
            return [self._load(session, recipe_id, available_names) for recipe_id in recipe_ids]

    @staticmethod
    def _load(session: Session, recipe_id: int, available_names: set[str]) -> RecipeRecommendation:
        recipe = session.get_one(Recipe, recipe_id)
        ingredients = session.exec(
            select(Ingredient.name)
            .join(RecipeIngredient)
            .where(RecipeIngredient.recipe_id == recipe_id)
            .group_by(Ingredient.ingredient_id, Ingredient.name)
            .order_by(func.min(RecipeIngredient.recipe_ingredient_id))
        ).all()
        steps = session.exec(
            select(RecipeStep.instruction)
            .where(RecipeStep.recipe_id == recipe_id)
            .order_by(RecipeStep.step_number)
        ).all()
        return RecipeRecommendation(
            id=recipe.recipe_id,
            name=recipe.name,
            time_minutes=_leading_int(recipe.cooking_time),
            servings=_leading_int(recipe.servings),
            ingredients=list(ingredients),
            steps=list(steps),
            missing=[item for item in ingredients if item not in available_names],
        )
