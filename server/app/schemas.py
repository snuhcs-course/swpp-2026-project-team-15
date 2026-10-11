# AI-generated with Claude Code (Opus 5.5), 2026-10-11; review pending by Jaehyuk Choi.
"""API contract between the Android client and the server."""

from pydantic import BaseModel, Field


class DetectedItem(BaseModel):
    """One item a vision provider reports; mirrors the 2026-09-30 Gemini benchmark output."""

    name_raw: str
    category: str
    confidence: float = Field(ge=0.0, le=1.0)


class IngredientCandidate(BaseModel):
    name: str
    raw_texts: list[str]
    confidence: float


class AnalyzeResponse(BaseModel):
    """Unconfirmed candidates: the user must review them before they enter the fridge."""

    candidates: list[IngredientCandidate]


class RecommendRequest(BaseModel):
    ingredients: list[str] = Field(description="Confirmed ingredient names from the fridge")
    # Source recipes need a median of 11 ingredients, so a strict 0-1 limit returns
    # almost nothing for a realistic fridge; results are ranked by missing count instead.
    max_missing: int = Field(default=3, ge=0, le=5)
    limit: int = Field(default=20, ge=1, le=100)


class RecipeRecommendation(BaseModel):
    id: int
    name: str
    time_minutes: int | None
    servings: int | None
    ingredients: list[str]
    steps: list[str]
    missing: list[str]


class RecommendResponse(BaseModel):
    staples_assumed: list[str]
    recipes: list[RecipeRecommendation]
