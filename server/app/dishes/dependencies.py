# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""The composition root of the dish services: the one place that creates the concrete classes.

``build_dish_service`` reads the settings once and wires the roles (roles.py) together. Services
receive what they need through their constructors and never create a model client, a video client
or a store themselves, so a test hands in fakes. There is one model provider today; a second one
is one more class and one more line in ``build_chat_model``.
"""

import os
from collections.abc import Mapping
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.dishes.catalog import Catalog
from app.dishes.llm import DEFAULT_MODEL, DishLLM
from app.dishes.recipe_names import RecipeNames
from app.dishes.recipes import CreditedRecipes, RecipeStore
from app.dishes.revision import Reviser
from app.dishes.roles import ChatModel, IngredientIndex, RecipeBook
from app.dishes.service import DishService
from app.dishes.video_search import WebSearchVideoSource
from app.dishes.video_store import VideoStore
from app.dishes.videos import VideoCache, VideoFinder, check_seconds
from app.dishes.youtube import YouTubeVerifier


def build_chat_model(env: Mapping[str, str], fallback_key: str = "") -> ChatModel | None:
    """The dish model, or None when no key is set (suggest and adapt then answer 502)."""
    key = env.get("DISH_LLM_API_KEY") or fallback_key
    if not key.strip():
        return None
    return DishLLM(key, env.get("DISH_LLM_MODEL") or DEFAULT_MODEL)


def build_video_finder(
    env: Mapping[str, str], model_key: str = "", *, dishes: int = 0, recipe_videos: int = 0
) -> VideoFinder | None:
    """None without a YouTube key. Without a model key only stored videos can be served.
    ``dishes`` and ``recipe_videos`` size how long a check of stored videos is reused."""
    youtube_key = env.get("YOUTUBE_API_KEY", "")
    if not youtube_key.strip():
        return None
    source = WebSearchVideoSource(model_key) if model_key.strip() else None
    return VideoFinder(
        YouTubeVerifier(youtube_key),
        VideoStore.load(env.get("DISH_VIDEOS")),
        VideoCache(),
        source,
        checked=VideoCache(ttl=check_seconds(dishes, recipe_videos)),
    )


def build_dish_service(env: Mapping[str, str] | None = None, model_key: str = "") -> DishService:
    """The service of the running app. ``model_key`` is the key of the general model settings."""
    env = os.environ if env is None else env
    catalog = Catalog.load()
    llm = build_chat_model(env, model_key)
    stored_recipes = RecipeStore.load(env.get("DISH_RECIPES"))
    recipes: RecipeBook = stored_recipes
    youtube_key = env.get("YOUTUBE_API_KEY", "")
    if youtube_key.strip():
        recipes = CreditedRecipes(recipes, YouTubeVerifier(youtube_key))
    # Recipe rows are matched with the reviewed name table, not the dish list's stand-ins
    # (research/experiments/dish_revision, round 3).
    reviser = Reviser(catalog, RecipeNames.load(), llm, recipes)
    key = env.get("DISH_LLM_API_KEY") or model_key
    return DishService(
        catalog,
        llm,
        build_video_finder(env, key, dishes=len(catalog), recipe_videos=len(stored_recipes)),
        recipes,
        reviser=reviser,
        index=catalog,
        assumed=catalog.staples,
    )


def get_dish_service(request: Request) -> DishService:
    return request.app.state.dish_service


DishServiceDep = Annotated[DishService, Depends(get_dish_service)]


def get_reviser(service: DishServiceDep) -> Reviser:
    if service.reviser is None:
        raise HTTPException(404, "No recipe for this dish")
    return service.reviser


def get_index(service: DishServiceDep) -> IngredientIndex:
    if service.index is None:
        raise HTTPException(404, "Ingredient list is not available")
    return service.index


ReviserDep = Annotated[Reviser, Depends(get_reviser)]
IndexDep = Annotated[IngredientIndex, Depends(get_index)]
