# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""The composition root of the dish services: the one place that creates the concrete classes.

``build_dish_parts`` reads the settings once and wires the roles (roles.py) together. Services
receive what they need through their constructors and never create a model client, a video client
or a store themselves, so a test hands in fakes. There is one model provider today; a second one
is one more class and one more line in ``build_chat_model``.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass
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


def dish_model_key(env: Mapping[str, str], fallback_key: str = "") -> str:
    """The key for the dish model and the video search: DISH_LLM_API_KEY, else the general one.
    The one place this rule is written, so both calls always use the same key."""
    return env.get("DISH_LLM_API_KEY") or fallback_key


def build_chat_model(env: Mapping[str, str], fallback_key: str = "") -> ChatModel | None:
    """The dish model, or None when no key is set (suggest and adapt then answer 502)."""
    key = dish_model_key(env, fallback_key)
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


@dataclass(frozen=True)
class DishParts:
    """What the dish routes need, built once at app start. Each route asks for its own part, so
    the dish service does not carry the reviser and the ingredient index for the router."""

    service: DishService
    reviser: Reviser | None = None
    index: IngredientIndex | None = None


def build_dish_parts(env: Mapping[str, str] | None = None, model_key: str = "") -> DishParts:
    """The parts of the running app. ``model_key`` is the key of the general model settings."""
    env = os.environ if env is None else env
    # One rule for who owns what: the reviewed name table decides on the cards, in the addition
    # suggestions and in the recipe view (research/experiments/server_review, finding 4).
    names = RecipeNames.load()
    catalog = Catalog.load(names=names)
    llm = build_chat_model(env, model_key)
    stored_recipes = RecipeStore.load(env.get("DISH_RECIPES"))
    recipes: RecipeBook = stored_recipes
    youtube_key = env.get("YOUTUBE_API_KEY", "")
    if youtube_key.strip():
        retry = check_seconds(len(catalog), len(stored_recipes))
        recipes = CreditedRecipes(recipes, YouTubeVerifier(youtube_key), retry_seconds=retry)
    reviser = Reviser(catalog, names, llm, recipes)
    key = dish_model_key(env, model_key)
    service = DishService(
        catalog,
        llm,
        build_video_finder(env, key, dishes=len(catalog), recipe_videos=len(stored_recipes)),
        recipes,
        assumed=catalog.staples,
        names=names,
    )
    return DishParts(service, reviser, catalog)


def get_dish_parts(request: Request) -> DishParts:
    return request.app.state.dishes


DishPartsDep = Annotated[DishParts, Depends(get_dish_parts)]


def get_dish_service(parts: DishPartsDep) -> DishService:
    return parts.service


DishServiceDep = Annotated[DishService, Depends(get_dish_service)]


def get_reviser(parts: DishPartsDep) -> Reviser:
    if parts.reviser is None:
        raise HTTPException(404, "No recipe for this dish")
    return parts.reviser


def get_index(parts: DishPartsDep) -> IngredientIndex:
    if parts.index is None:
        raise HTTPException(404, "Ingredient list is not available")
    return parts.index


ReviserDep = Annotated[Reviser, Depends(get_reviser)]
IndexDep = Annotated[IngredientIndex, Depends(get_index)]
