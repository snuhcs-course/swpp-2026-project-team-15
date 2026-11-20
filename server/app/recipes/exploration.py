"""Additive, read-only HE exploration. AI-assisted 2026-11-10; human review pending."""

from difflib import get_close_matches

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.recipes.constants import normalize_name, with_synonyms
from app.recipes.dependencies import RecipeRepositoryDep
from app.recipes.exclusions import is_supported_recipe
from app.recipes.models import Ingredient, Recipe, RecipeIngredient
from app.recipes.schemas import RecipeRecommendation

router = APIRouter(prefix="/recipes/explore", tags=["recipe-exploration"])


class ExploreRequest(BaseModel):
    ingredients: list[str] = Field(default_factory=list, max_length=500)
    query: str = Field(default="", max_length=100)
    seen_ids: list[int] = Field(default_factory=list, max_length=5000)
    limit: int = Field(default=20, ge=1, le=100)
    max_missing: int = Field(default=3, ge=0, le=5)


class UnregisteredIngredient(BaseModel):
    name: str
    suggestions: list[str]


class ExploreResponse(BaseModel):
    recipes: list[RecipeRecommendation]
    has_more: bool
    unregistered: list[UnregisteredIngredient]
    staples_assumed: list[str]


@router.get("/capabilities")
def capabilities() -> dict[str, bool]:
    return {"search_supported": True, "unseen_supported": True, "catalog_supported": True}


@router.get("/catalog")
def catalog(repository: RecipeRepositoryDep) -> dict:
    return {
        "items": [
            {"ingredient_id": key, "name": name}
            for key, name in sorted(repository.ingredient_catalog().items())
        ]
    }


@router.post("")
def explore(request: ExploreRequest, repository: RecipeRepositoryDep) -> ExploreResponse:
    names = repository.ingredient_catalog()
    by_normal = {normalize_name(name): name for name in names.values()}
    available = with_synonyms(request.ingredients) | with_synonyms(repository.staples)
    anchors = with_synonyms(request.ingredients) - with_synonyms(repository.staples)
    unregistered = [
        UnregisteredIngredient(
            name=name,
            suggestions=[
                by_normal[candidate]
                for candidate in get_close_matches(
                    normalize_name(name), list(by_normal), n=3, cutoff=0.5
                )
            ],
        )
        for name in dict.fromkeys(request.ingredients)
        if normalize_name(name) and not (with_synonyms([name]) & by_normal.keys())
    ]
    seen = set(request.seen_ids)
    query = normalize_name(request.query)
    with Session(repository._engine) as session:
        rows = session.exec(select(Recipe).order_by(Recipe.recipe_id)).all()
        needs: dict[int, set[str]] = {}
        for key, name in session.exec(
            select(RecipeIngredient.recipe_id, Ingredient.name).join(
                Ingredient, RecipeIngredient.ingredient_id == Ingredient.ingredient_id
            )
        ).all():
            needs.setdefault(key, set()).add(name)
        ranked = []
        for row in rows:
            if row.recipe_id in seen or not is_supported_recipe(row.name):
                continue
            required = needs.get(row.recipe_id, set())
            missing = sum(normalize_name(name) not in available for name in required)
            matched = sum(normalize_name(name) in anchors for name in required)
            if query:
                if query not in normalize_name(row.name):
                    continue
            elif not matched or missing > request.max_missing:
                continue
            ranked.append((missing, -matched, row.recipe_id))
        ranked.sort()
        actual_available = {name for name in names.values() if normalize_name(name) in available}
        result = [
            repository._load(session, key, actual_available)
            for _, _, key in ranked[: request.limit]
        ]
    return ExploreResponse(
        recipes=result,
        has_more=len(ranked) > request.limit,
        unregistered=unregistered,
        staples_assumed=list(repository.staples),
    )
