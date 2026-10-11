# AI-generated with Claude Code (Opus 5.5), 2026-10-11; review pending by Jaehyuk Choi.
"""Application factory. Collaborators are injected so tests can replace them.

Run: uv run --env-file .env uvicorn app.main:create_app_from_env --factory
"""

from fastapi import FastAPI
from google import genai

from app.config import Settings
from app.database import read_only_sqlite_engine
from app.recipes.router import router as recipes_router
from app.recipes.service import RecipeRepository
from app.vision.gemini import GeminiVisionProvider
from app.vision.providers import FixtureVisionProvider, VisionProvider
from app.vision.router import router as vision_router


def create_app(vision: VisionProvider, recipes: RecipeRepository) -> FastAPI:
    app = FastAPI(title="My Little Chef API", version="0.1.0")
    app.state.vision_provider = vision
    app.state.recipe_repository = recipes
    app.include_router(vision_router)
    app.include_router(recipes_router)

    @app.get("/health", tags=["health"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


def create_app_from_env() -> FastAPI:
    settings = Settings.from_env()
    recipes = RecipeRepository(read_only_sqlite_engine(settings.recipe_db_path))
    return create_app(_build_vision(settings), recipes)


def _build_vision(settings: Settings) -> VisionProvider:
    if settings.vision_provider == "gemini":
        client = genai.Client(api_key=settings.gemini_api_key)
        return GeminiVisionProvider(client, settings.gemini_model)
    return FixtureVisionProvider(settings.vision_fixture_dir)
