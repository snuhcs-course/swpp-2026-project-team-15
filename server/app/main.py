# AI-generated with Claude Code (Opus 5.5), 2026-10-11; review pending by Jaehyuk Choi.
"""HTTP layer. Collaborators are injected so tests can replace them.

Run: uv run --env-file .env uvicorn app.main:create_app_from_env --factory
"""

from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from google import genai

from app.config import Settings
from app.gemini_vision import GeminiVisionProvider
from app.recipes import RecipeRepository
from app.schemas import AnalyzeResponse, RecommendRequest, RecommendResponse
from app.vision import FixtureVisionProvider, VisionError, VisionProvider, to_candidates
from app.vocabulary import STAPLE_SEASONINGS

SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}


def create_app(vision: VisionProvider, recipes: RecipeRepository) -> FastAPI:
    app = FastAPI(title="My Little Chef API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/analyze")
    def analyze(image: Annotated[UploadFile, File()]) -> AnalyzeResponse:
        if image.content_type not in SUPPORTED_IMAGE_TYPES:
            raise HTTPException(415, f"Unsupported image type: {image.content_type}")
        data = image.file.read()
        if not data:
            raise HTTPException(422, "Empty image")
        try:
            items = vision.detect(data, image.content_type)
        except VisionError as exc:
            raise HTTPException(502, str(exc)) from exc
        return AnalyzeResponse(candidates=to_candidates(items))

    @app.post("/recipes/recommend")
    def recommend(request: RecommendRequest) -> RecommendResponse:
        return RecommendResponse(
            staples_assumed=list(STAPLE_SEASONINGS),
            recipes=recipes.recommend(request.ingredients, request.max_missing, request.limit),
        )

    return app


def create_app_from_env() -> FastAPI:
    settings = Settings.from_env()
    return create_app(_build_vision(settings), RecipeRepository(settings.recipe_db_path))


def _build_vision(settings: Settings) -> VisionProvider:
    if settings.vision_provider == "gemini":
        client = genai.Client(api_key=settings.gemini_api_key)
        return GeminiVisionProvider(client, settings.gemini_model)
    return FixtureVisionProvider(settings.vision_fixture_dir)
