# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Suggest, adapt and find videos for dishes the naive way: the model sees only the dish names and
the user's ingredients and answers with dishes plus what the user has and lacks. The service builds
the request (prompts.py), calls the model and has the answer checked (answers.py); it holds no
wording and no rules of its own. There is no rules fallback."""

from app.dishes.answers import (
    check_adapt,
    check_suggest,
    fewest_missing_first,
    search_url,
    strings,
)
from app.dishes.choices import ingredient_vocabulary, suggest_choices
from app.dishes.errors import MODEL_NOT_CONFIGURED, DishLLMError, VideoError
from app.dishes.prompts import adapt_request, suggest_request
from app.dishes.revision import Reviser
from app.dishes.roles import ChatModel, DishCatalog, IngredientIndex, RecipeBook
from app.dishes.schemas import AdaptResponse, SuggestResponse, VideosResponse
from app.dishes.videos import VideoFinder

NO_SUBSTITUTE = "냉장고 재료로는 마땅한 대체를 찾지 못했어요."


class DishService:
    def __init__(
        self,
        catalog: DishCatalog,
        llm: ChatModel | None = None,
        finder: VideoFinder | None = None,
        recipes: RecipeBook | None = None,
        reviser: Reviser | None = None,
        index: IngredientIndex | None = None,
        assumed: frozenset[str] = frozenset(),
    ):
        self.catalog = catalog
        self.llm = llm
        self.finder = finder
        self.recipes = recipes
        self.reviser = reviser
        self.index = index
        self.assumed = assumed
        self._vocabulary = ingredient_vocabulary(catalog.all())

    def suggest(self, ingredients: list[str]) -> SuggestResponse:
        """Raises DishLLMError when the model is missing or fails."""
        if self.llm is None:
            raise DishLLMError(MODEL_NOT_CONFIGURED)
        names = [d.name for d in self.catalog.all()]
        choices = suggest_choices(ingredients, names, self._vocabulary, self.assumed)
        request = suggest_request(choices)
        data = self.llm.complete(request.system, request.user, request.name, request.schema)
        dishes = fewest_missing_first(check_suggest(data, self.catalog, self.recipes, choices))
        return SuggestResponse(source="llm", dishes=dishes)

    def videos(self, dish_id: str) -> VideosResponse | None:
        """None when the dish is unknown. Raises VideoError when the lookup fails or is off."""
        dish = self.catalog.get(dish_id)
        if dish is None:
            return None
        if self.finder is None:
            raise VideoError(MODEL_NOT_CONFIGURED)
        videos, source = self.finder.lookup(dish_id, dish.name)
        return VideosResponse(
            dish_id=dish_id, videos=videos, search_url=search_url(dish.name), source=source
        )

    def adapt(
        self, dish_id: str, ingredients: list[str], missing: list[str]
    ) -> AdaptResponse | None:
        """None when the dish is unknown. Raises DishLLMError when the model call fails.

        The model names a substitute from the user's own ingredients (or none); the server only
        checks the JSON shape and that the substitute is one of those ingredients."""
        dish = self.catalog.get(dish_id)
        if dish is None:
            return None
        wanted = strings(missing)
        if not wanted:
            return AdaptResponse(
                dish_id=dish_id,
                substitutions=[],
                skip_ok=[],
                source="llm",
                note="부족한 재료가 없어요.",
            )
        if self.llm is None:
            raise DishLLMError(MODEL_NOT_CONFIGURED)
        owned = strings(ingredients)
        request = adapt_request(dish.name, wanted, owned)
        data = self.llm.complete(request.system, request.user, request.name, request.schema)
        subs = check_adapt(data, wanted, owned)
        return AdaptResponse(
            dish_id=dish_id,
            substitutions=subs,
            skip_ok=[],
            note="" if subs else NO_SUBSTITUTE,
            source="llm",
        )
