# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
from fastapi import APIRouter, HTTPException, status

from app.dishes.dependencies import DishServiceDep
from app.dishes.errors import DishLLMError, VideoError
from app.dishes.schemas import (
    AdaptRequest,
    AdaptResponse,
    DishInfo,
    DishList,
    IngredientCatalogResponse,
    IngredientSuggestion,
    IngredientSuggestionRequest,
    IngredientSuggestionResponse,
    RecipeRequest,
    RecipeView,
    ReviseRequest,
    ReviseResponse,
    SourceRecipe,
    SuggestRequest,
    SuggestResponse,
    VideosRequest,
    VideosResponse,
)
from app.schemas import ErrorResponse

router = APIRouter(prefix="/dishes", tags=["dishes"])
# The app's fridge screens call these two routes (paths kept from the earlier version); they are
# answered from the dish list.
ingredients_router = APIRouter(prefix="/recipes", tags=["ingredients"])


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
    "/suggest",
    summary="Dishes to cook from the ingredients at hand",
    operation_id="suggest_dishes",
    responses={502: {"model": ErrorResponse, "description": "The model call failed"}},
)
def suggest(body: SuggestRequest, service: DishServiceDep) -> SuggestResponse:
    try:
        return service.suggest(body.ingredients)
    except DishLLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc


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
        result = service.adapt(body.dish_id, body.ingredients, body.missing)
    except DishLLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    if result is None:
        raise HTTPException(422, "Unknown dish id")
    return result


@router.post(
    "/videos",
    summary="Videos to follow along for one dish, found on request",
    operation_id="dish_videos",
    responses={
        422: {"model": ErrorResponse, "description": "Unknown dish id"},
        502: {"model": ErrorResponse, "description": "The model or YouTube call failed"},
    },
)
def videos(body: VideosRequest, service: DishServiceDep) -> VideosResponse:
    try:
        result = service.videos(body.dish_id)
    except VideoError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    if result is None:
        raise HTTPException(422, "Unknown dish id")
    return result


@router.get(
    "/{dish_id}/recipe",
    summary="The stored recipe of one dish",
    operation_id="dish_recipe",
    responses={404: {"model": ErrorResponse, "description": "No recipe for this dish"}},
)
def recipe(dish_id: str, service: DishServiceDep) -> SourceRecipe:
    found = service.recipes.get(dish_id)
    if found is None:
        raise HTTPException(404, "No recipe for this dish")
    return found


@router.post(
    "/recipe",
    summary="The stored recipe with what the user has of each ingredient",
    operation_id="dish_recipe_view",
    responses={404: {"model": ErrorResponse, "description": "No recipe for this dish"}},
)
def recipe_view(body: RecipeRequest, service: DishServiceDep) -> RecipeView:
    view = service.reviser.view(body.dish_id, body.ingredients)
    if view is None:
        raise HTTPException(404, "No recipe for this dish")
    return view


@router.post(
    "/revise",
    summary="The recipe of one dish adapted to the ingredients the user has, or a refusal",
    operation_id="revise_dish",
    responses={
        404: {"model": ErrorResponse, "description": "No recipe for this dish"},
        502: {"model": ErrorResponse, "description": "The model call failed"},
    },
)
def revise(body: ReviseRequest, service: DishServiceDep) -> ReviseResponse:
    try:
        result = service.reviser.revise(body.dish_id, body.ingredients)
    except DishLLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    if result is None:
        raise HTTPException(404, "No recipe for this dish")
    return result


@ingredients_router.get(
    "/ingredients", summary="Ingredient names for entry completion", operation_id="dish_ingredients"
)
def ingredient_names(service: DishServiceDep) -> IngredientCatalogResponse:
    return IngredientCatalogResponse(names=service.catalog.ingredient_names())


@ingredients_router.post(
    "/ingredient-suggestions",
    summary="Ingredients that would complete the most dishes",
    operation_id="dish_ingredient_suggestions",
)
def ingredient_suggestions(
    body: IngredientSuggestionRequest, service: DishServiceDep
) -> IngredientSuggestionResponse:
    return IngredientSuggestionResponse(
        suggestions=[IngredientSuggestion(**s) for s in service.catalog.additions(body.ingredients)]
    )
