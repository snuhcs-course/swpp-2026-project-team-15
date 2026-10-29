# AI-assisted integration with Codex, 2026-10-29; human review pending.
# AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; reviewed by Jaehyuk Choi.

# Modified with Codex (GPT-6.1 Sol), 2026-10-17; reviewed by Soohyun An.
# Changes: Add the recommendations endpoint with input and database error handling.

from fastapi import APIRouter, HTTPException

from app.recipes.constants import STAPLE_SEASONINGS
from app.recipes.dependencies import RecipeRepositoryDep, RecommendationServiceDep
from app.recipes.recommendations import InvalidRevisionLimit
from app.recipes.schemas import (
    IngredientCatalogResponse,
    IngredientSuggestionRequest,
    IngredientSuggestionResponse,
    RecommendationsRequest,
    RecommendationsResponse,
    RecommendRequest,
    RecommendResponse,
)
from app.recipes.service import SourceUnavailable, UnknownIngredients

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.post("/recommend", summary="Recommend recipes for the fridge", operation_id="recommend")
def recommend(request: RecommendRequest, recipes: RecipeRepositoryDep) -> RecommendResponse:
    """Return recipes that use the given ingredients, fewest missing ingredients first."""
    return RecommendResponse(
        staples_assumed=list(STAPLE_SEASONINGS),
        recipes=recipes.recommend(request.ingredients, request.max_missing, request.limit),
    )


@router.post(
    "/recommendations",
    summary="Filter all recipes and revise selected candidates",
    operation_id="recommendations",
    responses={503: {"description": "Recipe source is unavailable"}},
)
def recommendations(
    request: RecommendationsRequest, service: RecommendationServiceDep
) -> RecommendationsResponse:
    """Return all candidates; client display sorting is independent of AI priority."""
    try:
        return service.recommend(request)
    except (UnknownIngredients, InvalidRevisionLimit):
        raise HTTPException(422, "Invalid ingredient IDs or revision limit") from None
    except SourceUnavailable:
        raise HTTPException(503, "Recipe source is unavailable") from None


@router.get("/ingredients", summary="List known ingredient names")
def ingredient_names(recipes: RecipeRepositoryDep) -> IngredientCatalogResponse:
    return IngredientCatalogResponse(names=recipes.ingredient_names())


@router.post("/ingredient-suggestions", summary="Suggest an ingredient that expands recipe options")
def ingredient_suggestions(
    request: IngredientSuggestionRequest, recipes: RecipeRepositoryDep
) -> IngredientSuggestionResponse:
    return IngredientSuggestionResponse(suggestions=recipes.ingredient_suggestions(request.ingredients))
