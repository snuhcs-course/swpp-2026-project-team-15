# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.

# Modified with Codex (GPT-6.1 Sol), 2026-10-17; reviewed by Soohyun An.
# Changes: Add dependency for the integrated recommendation service.

from typing import Annotated

from fastapi import Depends, Request

from app.recipes.recommendations import RecommendationService
from app.recipes.service import RecipeRepository


def get_recipe_repository(request: Request) -> RecipeRepository:
    return request.app.state.recipe_repository


RecipeRepositoryDep = Annotated[RecipeRepository, Depends(get_recipe_repository)]


def get_recommendation_service(request: Request) -> RecommendationService:
    return request.app.state.recommendation_service


RecommendationServiceDep = Annotated[RecommendationService, Depends(get_recommendation_service)]
