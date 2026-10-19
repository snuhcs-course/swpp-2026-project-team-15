"""Read-only integration boundary for versioned ingredient IDs and favorite originals."""

import hashlib
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, select

from app.recipes.dependencies import RecipeRepositoryDep
from app.recipes.models import Ingredient
from app.recipes.service import RecipeRepository, SourceUnavailable
from recipe_revision.models import SourceRecipe

router = APIRouter(prefix="/recipes", tags=["recipes"])


class CatalogIngredient(BaseModel):
    ingredient_id: int
    name: str


class IngredientCatalog(BaseModel):
    version: str
    ingredients: list[CatalogIngredient]


def read_catalog(repository: RecipeRepository) -> IngredientCatalog:
    try:
        with Session(repository._engine) as session:
            rows = session.exec(select(Ingredient).order_by(Ingredient.ingredient_id)).all()
        if not any(row.ingredient_id == 204 and row.name in {"물", "Water"} for row in rows):
            raise SourceUnavailable("Catalog does not match the water policy")
        values = [[row.ingredient_id, row.name] for row in rows]
        version = hashlib.sha256(
            json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()
        ).hexdigest()
        return IngredientCatalog(
            version=version,
            ingredients=[
                CatalogIngredient(ingredient_id=row.ingredient_id, name=row.name) for row in rows
            ],
        )
    except SQLAlchemyError:
        raise SourceUnavailable("Ingredient catalog is unavailable") from None


@router.get("/catalog", summary="Get the versioned ingredient catalog")
def ingredient_catalog(repository: RecipeRepositoryDep) -> IngredientCatalog:
    try:
        return read_catalog(repository)
    except SourceUnavailable:
        raise HTTPException(503, "Ingredient catalog is unavailable") from None


@router.get("/source/{recipe_id}", summary="Restore a saved recipe original without AI")
def recipe_source(recipe_id: int, repository: RecipeRepositoryDep) -> SourceRecipe:
    try:
        sources, _ = repository.load_catalog([], 204)
    except SourceUnavailable:
        raise HTTPException(503, "Recipe source is unavailable") from None
    source = next((row for row in sources if row.recipe_id == recipe_id), None)
    if source is None:
        raise HTTPException(404, "Recipe not found")
    return source
