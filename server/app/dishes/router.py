# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
from fastapi import APIRouter, HTTPException, status

from app.dishes.dependencies import DishServiceDep
from app.dishes.llm import DishLLMError
from app.dishes.schemas import (
    AdaptRequest,
    AdaptResponse,
    DishInfo,
    DishList,
    SuggestRequest,
    SuggestResponse,
)
from app.schemas import ErrorResponse

router = APIRouter(prefix="/dishes", tags=["dishes"])


@router.get("", summary="Baseline dish list", operation_id="list_dishes")
def list_dishes(service: DishServiceDep) -> DishList:
    dishes = [
        DishInfo(
            id=d.id,
            name=d.name,
            category=d.category,
            key_ingredients=list(d.key_ingredients),
            aliases=list(d.aliases),
        )
        for d in service.catalog.dishes.values()
    ]
    return DishList(dishes=dishes, count=len(dishes))


@router.post(
    "/suggest", summary="Dishes to cook from the ingredients at hand", operation_id="suggest_dishes"
)
def suggest(body: SuggestRequest, service: DishServiceDep) -> SuggestResponse:
    return service.suggest(body.ingredients, body.limit)


@router.post(
    "/adapt",
    summary="Substitutes or skips for the missing ingredients of one dish",
    operation_id="adapt_dish",
    responses={
        422: {"model": ErrorResponse, "description": "Unknown dish or invalid input"},
        502: {"model": ErrorResponse, "description": "The model call failed"},
    },
)
def adapt(body: AdaptRequest, service: DishServiceDep) -> AdaptResponse:
    try:
        result = service.adapt(body.dish_id, body.ingredients)
    except DishLLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    if result is None:
        raise HTTPException(422, "Unknown dish id")
    return result
