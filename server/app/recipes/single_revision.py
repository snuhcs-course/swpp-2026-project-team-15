"""Selected-dish revision, additive to main's batch API.

AI-assisted 2026-11-10; human review pending. One explicit request, at most one model call.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import BaseModel, Field, StrictBool, field_validator

from app.recipes.constants import normalize_name, with_synonyms
from app.recipes.dependencies import RecommendationServiceDep
from app.recipes.recommendations import public_error
from app.recipes.schemas import RecipeRevision
from app.recipes.service import SourceUnavailable
from recipe_revision.compact import available_ids as revision_available_ids
from recipe_revision.failures import Failure
from recipe_revision.models import SourceIngredient, SourceRecipe
from recipe_revision.pipeline import Steps, revise_with_steps

router = APIRouter(prefix="/recipes", tags=["selected-recipe-revision"])
Mode = Literal["mock", "live", "unknown"]
Name = Annotated[str, Field(min_length=1, max_length=100)]


class SelectedRevisionRequest(BaseModel):
    ingredients: list[Name] = Field(max_length=500)
    ignore_unregistered: StrictBool = False

    @field_validator("ingredients")
    @classmethod
    def meaningful_names(cls, values):
        if any(not normalize_name(value) for value in values):
            raise ValueError("Ingredient names must not be blank")
        return list(dict.fromkeys(values))


class SelectedRevisionResponse(BaseModel):
    recipe_id: int
    original: SourceRecipe
    original_missing: list[SourceIngredient]
    main_image_url: str | None
    revision: RecipeRevision
    provider_mode: Mode


@router.get("/revision-capabilities")
def capabilities(request: Request) -> dict:
    return {
        "selected_recipe_supported": True,
        "provider_mode": getattr(request.app.state, "revision_mode", "unknown"),
        "allergy_filter_supported": False,
        "utensil_filter_supported": False,
    }


@router.post("/{recipe_id}/revision", response_model=SelectedRevisionResponse)
def revise_selected(
    recipe_id: Annotated[int, Path(gt=0)],
    body: SelectedRevisionRequest,
    request: Request,
    service: RecommendationServiceDep,
) -> SelectedRevisionResponse:
    try:
        catalog = service.repository.ingredient_catalog()
        known = {normalize_name(name) for name in catalog.values()}
        unknown = [name for name in body.ingredients if not (with_synonyms([name]) & known)]
        if unknown and not body.ignore_unregistered:
            raise HTTPException(422, {"code": "unregistered_ingredients", "names": unknown})
        available_names = with_synonyms([name for name in body.ingredients if name not in unknown])
        ids = [key for key, name in catalog.items() if normalize_name(name) in available_names]
        sources, inventory = service.repository.load_catalog(ids, service.policy.water_id)
        source = next((row for row in sources if row.recipe_id == recipe_id), None)
        if source is None:
            raise HTTPException(404, "Recipe is not available")
        image = service.repository.load_image_urls([recipe_id]).get(recipe_id)
    except SourceUnavailable:
        raise HTTPException(503, "Recipe source is unavailable") from None

    available_ids = revision_available_ids(source, inventory, seasonings=service.policy.seasonings)
    missing = list(
        {
            item.ingredient_id: item
            for item in source.ingredients
            if item.ingredient_id not in available_ids
        }.values()
    )
    try:
        llm = service.llm_factory()
    except Exception:
        revision = RecipeRevision(
            status="failed", error=public_error(Failure("configuration", "configuration"))
        )
    else:
        try:
            outcome = revise_with_steps(
                source,
                inventory,
                llm,
                Steps(
                    prescreen=service.policy.prescreen != "off",
                    retry=False,
                    complete_changes=service.policy.complete_changes,
                    seasonings=service.policy.seasonings,
                ),
            )
            if outcome.status in ("revised", "refused"):
                revision = RecipeRevision(status=outcome.status, result=outcome.model_result)
            else:
                revision = RecipeRevision(
                    status="failed",
                    error=public_error(outcome.failure or Failure("internal", "revision")),
                )
        except Exception:
            revision = RecipeRevision(
                status="failed", error=public_error(Failure("internal", "revision"))
            )
    return SelectedRevisionResponse(
        recipe_id=recipe_id,
        original=source,
        original_missing=missing,
        main_image_url=image,
        revision=revision,
        provider_mode=getattr(request.app.state, "revision_mode", "unknown"),
    )
