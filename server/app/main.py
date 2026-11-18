# AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; reviewed by Jaehyuk Choi.

# Modified with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
# Changes: Serve dishes and recognition only; the recipe database and its routes are gone.

"""Application factory. Collaborators are injected so tests can replace them.

Run: uv run --env-file .env uvicorn app.main:create_app_from_env --factory
"""

import logging
import os

from fastapi import FastAPI, HTTPException
from google import genai
from google.genai import types

from app.config import Settings
from app.dishes.catalog import Catalog
from app.dishes.llm import DEFAULT_MODEL, DishLLM
from app.dishes.recipes import RecipeStore
from app.dishes.router import ingredients_router
from app.dishes.router import router as dishes_router
from app.dishes.service import DishService
from app.dishes.video_search import WebSearchVideoSource
from app.dishes.video_store import VideoStore
from app.dishes.videos import VideoCache, VideoFinder
from app.dishes.youtube import YouTubeVerifier
from app.vision.gemini import REQUEST_TIMEOUT_MS, GeminiVisionProvider
from app.vision.openrouter import OpenRouterVisionProvider
from app.vision.providers import FixtureVisionProvider, VisionProvider
from app.vision.router import router as vision_router


def create_app(vision: VisionProvider, dishes: DishService | None = None) -> FastAPI:
    app = FastAPI(
        title="My Little Chef API",
        version="0.2.0",
        description="Ingredient recognition and dish suggestions for one-person households.",
    )
    app.state.vision_provider = vision
    app.state.dish_service = dishes if dishes is not None else DishService(Catalog.load())
    app.include_router(vision_router)
    app.include_router(dishes_router)
    app.include_router(ingredients_router)

    @app.get("/health", tags=["health"], summary="Liveness check")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["health"], summary="Dish list readiness")
    def ready() -> dict[str, str]:
        if not len(app.state.dish_service.catalog):
            raise HTTPException(503, "Dish list is empty")
        return {"status": "ready"}

    return app


def _dish_service(settings: Settings) -> DishService:
    key = os.environ.get("DISH_LLM_API_KEY") or settings.openrouter_api_key
    model = os.environ.get("DISH_LLM_MODEL") or DEFAULT_MODEL
    llm = DishLLM(key, model) if key.strip() else None
    youtube_key = os.environ.get("YOUTUBE_API_KEY", "")
    finder = None
    if youtube_key.strip():
        source = WebSearchVideoSource(key) if key.strip() else None
        finder = VideoFinder(
            YouTubeVerifier(youtube_key),
            VideoStore.load(os.environ.get("DISH_VIDEOS")),
            VideoCache(),
            source,
        )
    recipes = RecipeStore.load(os.environ.get("DISH_RECIPES"))
    return DishService(Catalog.load(), llm, finder, recipes)


def create_app_from_env() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # its INFO lines print full request URLs
    settings = Settings.from_env()
    return create_app(_build_vision(settings), _dish_service(settings))


def _build_vision(settings: Settings) -> VisionProvider:
    if settings.vision_provider == "openrouter":
        return OpenRouterVisionProvider(
            settings.openrouter_api_key, settings.openrouter_vision_model
        )
    if settings.vision_provider == "gemini":
        client = genai.Client(
            api_key=settings.gemini_api_key,
            http_options=types.HttpOptions(timeout=REQUEST_TIMEOUT_MS),
        )
        return GeminiVisionProvider(client, settings.gemini_model)
    return FixtureVisionProvider(settings.vision_fixture_dir)
