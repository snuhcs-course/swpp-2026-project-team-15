# AI-generated with Claude Code (Opus 5.5), 2026-10-11; review pending by Jaehyuk Choi.
from sqlmodel import Field, SQLModel


class RecommendRequest(SQLModel):
    ingredients: list[str] = Field(description="Confirmed ingredient names from the fridge")
    # Source recipes need a median of 11 ingredients, so a strict 0-1 limit returns
    # almost nothing for a realistic fridge; results are ranked by missing count instead.
    max_missing: int = Field(default=3, ge=0, le=5)
    limit: int = Field(default=20, ge=1, le=100)


class RecipeRecommendation(SQLModel):
    id: int
    name: str
    time_minutes: int | None
    servings: int | None
    ingredients: list[str]
    steps: list[str]
    missing: list[str]


class RecommendResponse(SQLModel):
    staples_assumed: list[str]
    recipes: list[RecipeRecommendation]
