# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.

# Modified with Codex (GPT-6.1 Sol), 2026-10-17; reviewed by Soohyun An.
# Changes: Add read-only loading and validation of recipes and inventory, including water.

"""Read-only recipe queries over the database built by server/db/import_recipes.py."""

import re
from collections import defaultdict

from sqlalchemy import Engine, case, func, text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from app.recipes.constants import STAPLE_SEASONINGS, with_synonyms
from app.recipes.models import Ingredient, Recipe, RecipeIngredient, RecipeStep
from app.recipes.schemas import RecipeRecommendation
from recipe_revision.models import InventoryIngredient, SourceIngredient, SourceRecipe, SourceStep

_LEADING_NUMBER = re.compile(r"\d+")


class UnknownIngredients(ValueError):
    """The submitted inventory includes unregistered IDs."""


class SourceUnavailable(RuntimeError):
    """A trustworthy complete source snapshot cannot be read."""


def _leading_int(text: str | None) -> int | None:
    match = _LEADING_NUMBER.match(text or "")
    return int(match.group()) if match else None


class RecipeRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def load_catalog(
        self, ingredient_ids: list[int], water_id: int
    ) -> tuple[tuple[SourceRecipe, ...], tuple[InventoryIngredient, ...]]:
        """Read all source rows and effective inventory in one read-only snapshot.

        Separate row queries preserve repeated ingredient IDs without multiplying
        steps. The session closes before external work starts.
        """
        try:
            with Session(self._engine) as session:
                if self._engine.dialect.name == "sqlite":
                    session.exec(text("BEGIN"))
                catalog = {
                    row.ingredient_id: row.name for row in session.exec(select(Ingredient)).all()
                }
                if set(ingredient_ids) - catalog.keys():
                    raise UnknownIngredients("Inventory contains unregistered ingredient IDs")
                if water_id not in catalog:
                    raise SourceUnavailable("Required water ingredient is unavailable")
                inventory = tuple(
                    InventoryIngredient(key, catalog[key])
                    for key in dict.fromkeys([*ingredient_ids, water_id])
                )
                rows = session.exec(select(Recipe).order_by(Recipe.recipe_id)).all()
                recipe_ids = {row.recipe_id for row in rows}
                ingredients = defaultdict(list)
                for row in session.exec(
                    select(RecipeIngredient).order_by(RecipeIngredient.recipe_ingredient_id)
                ).all():
                    if row.recipe_id not in recipe_ids or row.ingredient_id not in catalog:
                        raise SourceUnavailable("Invalid ingredient relationship")
                    ingredients[row.recipe_id].append(
                        SourceIngredient(
                            row.recipe_ingredient_id,
                            row.ingredient_id,
                            catalog[row.ingredient_id],
                            row.quantity_text,
                            row.ingredient_type_code,
                            row.ingredient_type,
                            row.original_name,
                        )
                    )
                steps = defaultdict(list)
                for row in session.exec(
                    select(RecipeStep).order_by(RecipeStep.step_number, RecipeStep.step_id)
                ).all():
                    if row.recipe_id not in recipe_ids:
                        raise SourceUnavailable("Invalid step relationship")
                    steps[row.recipe_id].append(
                        SourceStep(row.step_id, row.step_number, row.instruction, row.tip)
                    )
                sources = []
                for row in rows:
                    if not ingredients[row.recipe_id] or not steps[row.recipe_id]:
                        raise SourceUnavailable("Recipe source is incomplete")
                    sources.append(
                        SourceRecipe(
                            **row.model_dump(),
                            ingredients=tuple(ingredients[row.recipe_id]),
                            steps=tuple(steps[row.recipe_id]),
                        )
                    )
                return tuple(sources), inventory
        except SQLAlchemyError:
            raise SourceUnavailable("Recipe database is unavailable") from None

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
