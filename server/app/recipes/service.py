# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.

# Modified with Codex (GPT-6.1 Sol), 2026-10-17; reviewed by Soohyun An.
# Changes: Add read-only loading and validation of recipes and inventory, including water.

# Modified with Codex (GPT-6 Luna), 2026-11-03; reviewed by Ahyoon Choi.
# Changes: Load recipe image URLs for both response flows while keeping revision source records image-free.

"""Read-only recipe queries over the database built by server/db/import_recipes.py."""

import re
from collections import defaultdict
from collections.abc import Sequence

from sqlalchemy import Engine, case, func, text
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from app.recipes.constants import STAPLE_SEASONINGS, with_synonyms
from app.recipes.models import Ingredient, Recipe, RecipeIngredient, RecipeStep
from app.recipes.schemas import IngredientSuggestion, RecipeRecommendation
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
    def __init__(self, engine: Engine, staples: Sequence[str] = STAPLE_SEASONINGS) -> None:
        """``staples``: seasoning names assumed to be at home on the name-based paths.

        The app passes the names of the shared seasoning policy
        (``app.recipes.seasonings.resolve_staple_names``); the default is the original team list,
        so existing callers behave as before.
        """
        self._engine = engine
        self._staples = tuple(staples)

    @property
    def staples(self) -> tuple[str, ...]:
        return self._staples

    def ingredient_names(self) -> list[str]:
        """Names available for client entry completion."""
        with Session(self._engine) as session:
            return sorted(set(session.exec(select(Ingredient.name)).all()))

    def ingredient_labels(self) -> list[tuple[int, str, str | None, str | None]]:
        """Distinct (ingredient id, name, type code, type text) rows, to find which ingredients the
        recipes label as seasoning."""
        with Session(self._engine) as session:
            rows = session.exec(
                select(
                    Ingredient.ingredient_id,
                    Ingredient.name,
                    RecipeIngredient.ingredient_type_code,
                    RecipeIngredient.ingredient_type,
                )
                .join(RecipeIngredient, RecipeIngredient.ingredient_id == Ingredient.ingredient_id)
                .distinct()
            ).all()
        return [tuple(row) for row in rows]

    def ingredient_catalog(self) -> dict[int, str]:
        """Ingredient id to name, for validating configuration at startup."""
        with Session(self._engine) as session:
            return {row.ingredient_id: row.name for row in session.exec(select(Ingredient)).all()}

    def ingredient_suggestions(
        self, fridge: list[str], min_recipe_count: int = 5, limit: int = 5
    ) -> list[IngredientSuggestion]:
        """Rank one-ingredient additions by newly ready meals, then source recipe frequency."""
        staples = set(self._staples)
        available = with_synonyms(fridge) | staples
        owned_anchors = available - staples

        with Session(self._engine) as session:
            recipe_names = dict(session.exec(select(Recipe.recipe_id, Recipe.name)).all())
            ingredient_rows = session.exec(
                select(RecipeIngredient.recipe_id, Ingredient.name).join(
                    Ingredient, RecipeIngredient.ingredient_id == Ingredient.ingredient_id
                )
            ).all()

        required_by_recipe: dict[int, set[str]] = {}
        recipe_ids_by_name: dict[str, set[int]] = {}
        for recipe_id, name in ingredient_rows:
            required_by_recipe.setdefault(recipe_id, set()).add(name)
            recipe_ids_by_name.setdefault(name, set()).add(recipe_id)

        groups = {frozenset(with_synonyms([name])) for name in recipe_ids_by_name}
        suggestions: list[IngredientSuggestion] = []
        for group in groups:
            if group <= available or any(group < other for other in groups):
                continue
            covered_ids = set().union(*(recipe_ids_by_name.get(name, set()) for name in group))
            if len(covered_ids) < min_recipe_count:
                continue
            display_name = min(
                (
                    name
                    for name in group
                    if name in recipe_ids_by_name and frozenset(with_synonyms([name])) == group
                ),
                key=lambda name: (-len(recipe_ids_by_name[name]), len(name), name),
            )
            anchors_after = owned_anchors | (set(group) - staples)
            available_after = available | set(group)
            ready_ids = sorted(
                recipe_id
                for recipe_id in covered_ids
                if required_by_recipe[recipe_id] <= available_after
                and not required_by_recipe[recipe_id] <= available
                and required_by_recipe[recipe_id] & anchors_after
            )
            suggestions.append(
                IngredientSuggestion(
                    name=display_name,
                    ready_recipe_count=len(ready_ids),
                    recipe_count=len(covered_ids),
                    ready_recipe_names=[recipe_names[recipe_id] for recipe_id in ready_ids[:3]],
                )
            )

        suggestions.sort(key=lambda item: (-item.ready_recipe_count, -item.recipe_count, item.name))
        return suggestions[:limit]

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
                            **row.model_dump(exclude={"main_image_url"}),
                            ingredients=tuple(ingredients[row.recipe_id]),
                            steps=tuple(steps[row.recipe_id]),
                        )
                    )
                return tuple(sources), inventory
        except SQLAlchemyError:
            raise SourceUnavailable("Recipe database is unavailable") from None

    def load_image_urls(self, recipe_ids: list[int]) -> dict[int, str | None]:
        """Read image URLs separately so revision source records stay image-free."""
        if not recipe_ids:
            return {}
        try:
            with Session(self._engine) as session:
                rows = session.exec(
                    select(Recipe.recipe_id, Recipe.main_image_url).where(
                        col(Recipe.recipe_id).in_(recipe_ids)
                    )
                ).all()
                return {recipe_id: image_url for recipe_id, image_url in rows}
        except SQLAlchemyError:
            raise SourceUnavailable("Recipe database is unavailable") from None

    def recommend(
        self, fridge: list[str], max_missing: int, limit: int
    ) -> list[RecipeRecommendation]:
        staples = set(self._staples)
        fridge_names = with_synonyms(fridge) - staples
        available_names = fridge_names | staples

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
            main_image_url=recipe.main_image_url,
        )
