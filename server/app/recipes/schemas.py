# AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; reviewed by Jaehyuk Choi.

# Modified with Codex (GPT-6.1 Sol), 2026-10-17; reviewed by Soohyun An.
# Changes: Define and validate ID-based requests, recipe results, revision statuses, and errors.

from typing import Annotated, Literal

from pydantic import BaseModel, field_validator, model_validator
from pydantic import Field as PydanticField
from sqlmodel import Field, SQLModel

from app.recipes.policy import DEFAULT_POLICY
from recipe_revision.failures import FailureCode, FailureStage
from recipe_revision.models import SourceRecipe


class RecommendRequest(SQLModel):
    ingredients: list[str] = Field(
        description="Confirmed ingredient names from the fridge",
        schema_extra={"examples": [["달걀", "대파", "밥"]]},
    )
    # Source recipes need a median of 11 ingredients, so a strict 0-1 limit returns
    # almost nothing for a realistic fridge; results are ranked by missing count instead.
    max_missing: int = Field(
        default=3, ge=0, le=5, description="Most ingredients a recipe may lack (staples aside)"
    )
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of recipes")


class RecipeRecommendation(SQLModel):
    id: int
    name: str
    time_minutes: int | None
    servings: int | None
    ingredients: list[str]
    steps: list[str]
    missing: list[str] = Field(description="Ingredients beyond the fridge and staples")


class RecommendResponse(SQLModel):
    staples_assumed: list[str] = Field(description="Seasonings assumed to be at home")
    recipes: list[RecipeRecommendation]


PositiveID = Annotated[int, PydanticField(strict=True, gt=0)]


class RecommendationsRequest(BaseModel):
    """Explicit registered inventory; revision_limit bounds attempts, not returned recipes."""

    ingredient_ids: list[PositiveID]
    revision_limit: Annotated[int, PydanticField(strict=True, ge=1, le=5)] = (
        DEFAULT_POLICY.default_revision_limit
    )

    @field_validator("ingredient_ids")
    @classmethod
    def distinct_ids(cls, values: list[int]) -> list[int]:
        return list(dict.fromkeys(values))


class RevisionError(BaseModel):
    code: FailureCode
    stage: FailureStage
    message: str
    http_status: int | None = None
    scope: Literal["individual", "shared"]


class RevisedIngredient(BaseModel):
    ingredient_id: int
    name: str
    quantity_text: str | None


class RevisedStep(BaseModel):
    step_number: int
    instruction: str
    tip: str | None


class RevisedRecipe(BaseModel):
    name: str
    servings: str | None
    ingredients: list[RevisedIngredient] = PydanticField(min_length=1)
    steps: list[RevisedStep] = PydanticField(min_length=1)


class RevisionChange(BaseModel):
    kind: Literal["omission", "substitution", "quantity", "servings", "step"]
    reason: str
    source_ingredient_row_ids: list[int]
    source_step_ids: list[int]


class ModelResult(BaseModel):
    """Typed representation of the existing parsed model result, without semantic repair."""

    can_revise: bool
    reason: str
    changes: list[RevisionChange]
    revised_recipe: RevisedRecipe | None

    @model_validator(mode="after")
    def consistent_branch(self):
        if self.can_revise:
            if self.revised_recipe is None:
                raise ValueError("Revised result requires a recipe")
        elif self.revised_recipe is not None or self.changes or not self.reason.strip():
            raise ValueError("Refused result requires only a meaningful reason")
        return self


class RecipeRevision(BaseModel):
    """An attempted judgment/error or an explicit reason for not attempting."""

    status: Literal["revised", "refused", "failed", "not_attempted"]
    result: ModelResult | None = None
    error: RevisionError | None = None
    not_attempted_reason: Literal["outside_revision_limit", "shared_failure"] | None = None

    @model_validator(mode="after")
    def consistent_outcome(self):
        if self.status in ("revised", "refused"):
            valid = (
                self.result is not None
                and self.error is None
                and self.not_attempted_reason is None
                and self.result.can_revise == (self.status == "revised")
            )
        elif self.status == "failed":
            valid = (
                self.result is None and self.error is not None and self.not_attempted_reason is None
            )
        else:
            valid = (
                self.result is None and self.error is None and self.not_attempted_reason is not None
            )
        if not valid:
            raise ValueError("Revision fields do not match the status")
        return self


class FilteringCounts(BaseModel):
    matched_count: int
    missing_count: int
    main_matched_count: int


class RecommendationEntry(BaseModel):
    recipe_id: int
    original: SourceRecipe
    filtering: FilteringCounts
    revision: RecipeRevision


class RevisionSummary(BaseModel):
    limit: int
    selected_count: int
    attempted_count: int
    stopped_error: RevisionError | None = None


class RecommendationsResponse(BaseModel):
    """Full filtered catalog; array order is not a client display-sort contract."""

    recipes: list[RecommendationEntry]
    revision_summary: RevisionSummary
    assumed_ingredient_ids: list[int]
