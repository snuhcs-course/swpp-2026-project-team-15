# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
from typing import Annotated

from fastapi import Depends, Request

from app.recipes.service import RecipeRepository


def get_recipe_repository(request: Request) -> RecipeRepository:
    return request.app.state.recipe_repository


RecipeRepositoryDep = Annotated[RecipeRepository, Depends(get_recipe_repository)]
