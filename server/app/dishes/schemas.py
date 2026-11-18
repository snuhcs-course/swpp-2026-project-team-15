# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
from typing import Literal

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
    has_recipe: bool = False


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


class RecipeIngredient(BaseModel):
    name: str
    amount: str | None = None
    role: Literal["main", "secondary", "seasoning"] = "secondary"


class RecipeStep(BaseModel):
    n: int
    text: str


class RecipeVideo(BaseModel):
    id: str
    title: str
    channel: str


class SourceRecipe(BaseModel):
    """A recipe written down from one video (the stored source of a revision)."""

    dish_id: str
    video: RecipeVideo | None = None
    source: str = "ai_structured_from_captions"
    generated_at: str = ""
    servings: int | None = None
    ingredients: list[RecipeIngredient]
    steps: list[RecipeStep]
    tips: list[str] = Field(default_factory=list)
    uncertain: list[str] = Field(default_factory=list)
    caption_gaps: bool = False


class RecipeRequest(BaseModel):
    dish_id: str = Field(min_length=1, max_length=80)
    ingredients: list[str] = Field(default_factory=list, max_length=60)


class RecipeView(BaseModel):
    dish_id: str
    name: str
    recipe: SourceRecipe
    availability: list[Literal["owned", "assumed", "unavailable"]] = Field(
        description="One entry per recipe ingredient, in order"
    )


class ReviseRequest(BaseModel):
    dish_id: str = Field(min_length=1, max_length=80)
    ingredients: list[str] = Field(min_length=1, max_length=60)


class RevisedIngredient(BaseModel):
    name: str
    amount: str | None = None


class RevisedRecipe(BaseModel):
    servings: int | None = None
    ingredients: list[RevisedIngredient]
    steps: list[RecipeStep]
    tips: list[str] = Field(default_factory=list)


class Change(BaseModel):
    reason: str
    ingredient_refs: list[int] = Field(description="1-based rows of the original ingredients")
    step_refs: list[int] = Field(description="1-based numbers of the original steps")


class RevisionError(BaseModel):
    code: str
    message: str


class ReviseResponse(BaseModel):
    status: Literal["revised", "refused", "failed"]
    dish_id: str
    original: SourceRecipe
    availability: list[Literal["owned", "assumed", "unavailable"]]
    revised: RevisedRecipe | None = None
    changes: list[Change] = Field(default_factory=list)
    refusal_reason: str | None = None
    error: RevisionError | None = None
    notice: str = "AI가 만든 제안이에요. 맛과 알레르기는 직접 확인해 주세요."
