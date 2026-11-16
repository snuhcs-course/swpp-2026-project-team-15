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
    thumbnail_url: str


class SuggestRequest(BaseModel):
    ingredients: list[str] = Field(min_length=1, max_length=60)


class SuggestedDish(BaseModel):
    id: str
    name: str
    category: str
    have: list[str]
    missing: list[str]
    search_url: str


class SuggestResponse(BaseModel):
    source: str
    dishes: list[SuggestedDish]


class VideosRequest(BaseModel):
    dish_id: str = Field(min_length=1, max_length=80)


class VideosResponse(BaseModel):
    dish_id: str
    videos: list[Video]
    search_url: str


class AdaptRequest(BaseModel):
    dish_id: str = Field(min_length=1, max_length=80)
    ingredients: list[str] = Field(min_length=1, max_length=60)
    missing: list[str] = Field(default_factory=list, max_length=20)


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


class IngredientCatalogResponse(BaseModel):
    names: list[str]


class IngredientSuggestionRequest(BaseModel):
    ingredients: list[str] = Field(description="Confirmed names in the user's fridge")


class IngredientSuggestion(BaseModel):
    name: str
    ready_recipe_count: int
    recipe_count: int
    ready_recipe_names: list[str]


class IngredientSuggestionResponse(BaseModel):
    suggestions: list[IngredientSuggestion]
