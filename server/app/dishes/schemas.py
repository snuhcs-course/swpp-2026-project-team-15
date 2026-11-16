# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
from pydantic import BaseModel, Field


class DishInfo(BaseModel):
    id: str
    name: str
    category: str
    key_ingredients: list[str]
    aliases: list[str]


class DishList(BaseModel):
    dishes: list[DishInfo]
    count: int


class Video(BaseModel):
    video_id: str
    title: str
    channel: str
    view_count: int | None = None
    thumbnail_url: str
    embeddable: bool = True


class SuggestRequest(BaseModel):
    ingredients: list[str] = Field(min_length=1, max_length=60)
    limit: int = Field(default=5, ge=1, le=8)


class SuggestedDish(BaseModel):
    id: str
    name: str
    category: str
    have: list[str]
    missing: list[str]
    reason: str
    keywords: list[str]
    videos: list[Video]
    search_url: str


class SuggestResponse(BaseModel):
    source: str
    dishes: list[SuggestedDish]


class AdaptRequest(BaseModel):
    dish_id: str = Field(min_length=1, max_length=80)
    ingredients: list[str] = Field(min_length=1, max_length=60)


class Substitution(BaseModel):
    missing: str
    suggestion: str
    uses: list[str]


class AdaptResponse(BaseModel):
    dish_id: str
    substitutions: list[Substitution]
    skip_ok: list[str]
    note: str
    source: str
