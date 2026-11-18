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
from app.dishes.dependencies import build_dish_service
from app.dishes.router import ingredients_router
from app.dishes.router import router as dishes_router
from app.dishes.service import DishService
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
    app.state.dish_service = dishes if dishes is not None else build_dish_service({})
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


def create_app_from_env() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # its INFO lines print full request URLs
    settings = Settings.from_env()
    return create_app(
        _build_vision(settings), build_dish_service(os.environ, settings.openrouter_api_key)
    )


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
