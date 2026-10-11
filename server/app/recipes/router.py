# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
from fastapi import APIRouter

from app.recipes.constants import STAPLE_SEASONINGS
from app.recipes.dependencies import RecipeRepositoryDep
from app.recipes.schemas import RecommendRequest, RecommendResponse

router = APIRouter(prefix="/recipes", tags=["recipes"])


@router.post("/recommend")
def recommend(request: RecommendRequest, recipes: RecipeRepositoryDep) -> RecommendResponse:
    return RecommendResponse(
        staples_assumed=list(STAPLE_SEASONINGS),
        recipes=recipes.recommend(request.ingredients, request.max_missing, request.limit),
    )
