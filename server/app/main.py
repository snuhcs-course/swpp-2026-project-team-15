# AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; reviewed by Jaehyuk Choi.

# Modified with Codex (GPT-6.1 Sol), 2026-10-17; reviewed by Soohyun An.
# Changes: Wire the recommendation service and provider while preserving existing app creation.

# Modified with Codex (GPT-6 Luna), 2026-11-03; reviewed by Ahyoon Choi.
# Changes: Mount local recipe images at /recipe-images.
# Modified with Codex (GPT-6), 2026-11-06; reviewed by Ahyoon Choi.
# Changes: Serve recipe images from server/static/images/recipes.
# Modified with Codex (GPT-6), 2026-11-06; reviewed by Ahyoon Choi.
# Changes: Name the recipe image directory for static-route coverage.

"""Application factory. Collaborators are injected so tests can replace them.

Run: uv run --env-file .env uvicorn app.main:create_app_from_env --factory
"""

import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from google import genai
from google.genai import types

from app.config import Settings
from app.database import recipe_engine
from app.recipes.policy import RecommendationPolicy
from app.recipes.providers import revision_factory
from app.recipes.recommendations import RecommendationService
from app.recipes.router import router as recipes_router
from app.recipes.seasonings import (
    load_seasoning_policy,
    resolve_staple_names,
    seasoning_labelled_ids,
    validate_against_catalog,
)
from app.recipes.service import RecipeRepository, SourceUnavailable
from app.vision.gemini import REQUEST_TIMEOUT_MS, GeminiVisionProvider
from app.vision.openrouter import OpenRouterVisionProvider
from app.vision.providers import FixtureVisionProvider, VisionProvider
from app.vision.router import router as vision_router

RECIPE_IMAGE_DIR = Path(__file__).resolve().parents[1] / "static" / "images" / "recipes"


def create_app(
    vision: VisionProvider,
    recipes: RecipeRepository,
    *,
    recommendations: RecommendationService | None = None,
) -> FastAPI:
    app = FastAPI(
        title="My Little Chef API",
        version="0.1.0",
        description="Ingredient recognition and recipe recommendation for one-person households.",
    )
    app.mount(
        "/recipe-images",
        StaticFiles(directory=RECIPE_IMAGE_DIR, check_dir=False),
        name="recipe-images",
    )
    app.state.vision_provider = vision
    app.state.recipe_repository = recipes
    app.state.recommendation_service = (
        recommendations if recommendations is not None else RecommendationService(recipes)
    )
    app.include_router(vision_router)
    app.include_router(recipes_router)

    @app.get("/health", tags=["health"], summary="Liveness check")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready", tags=["health"], summary="Database and recipe readiness")
    def ready() -> dict[str, str]:
        try:
            sources, _ = recipes.load_catalog([], 204)
            if not sources:
                raise SourceUnavailable("Empty recipe source")
        except SourceUnavailable:
            raise HTTPException(503, "Recipe database is not ready") from None
        return {"status": "ready"}

    return app


def create_app_from_env() -> FastAPI:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
    settings = Settings.from_env()
    engine = recipe_engine(settings.database_url, settings.recipe_db_path)
    recipes = RecipeRepository(engine)
    seasonings = load_seasoning_policy()
    catalog = recipes.ingredient_catalog()
    validate_against_catalog(seasonings, catalog)
    # The name-based endpoints read the same policy, so one edit changes every path.
    all_mode = seasonings.mode == "all"
    labelled = seasoning_labelled_ids(recipes.ingredient_labels()) if all_mode else ()
    recipes = RecipeRepository(engine, staples=resolve_staple_names(seasonings, catalog, labelled))
    logging.getLogger(__name__).info("assumed seasonings: %s", seasonings.describe())
    return create_app(
        _build_vision(settings),
        recipes,
        recommendations=RecommendationService(
            recipes,
            policy=RecommendationPolicy.from_env(os.environ, seasonings=seasonings),
            llm_factory=revision_factory(settings),
        ),
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
