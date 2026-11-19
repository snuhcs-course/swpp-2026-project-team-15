# AI-generated with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
"""Revise a stored recipe so it uses only what the user has, or refuse.

The server decides what is available (owned, a staple assumed at home, or unavailable) and refuses
without a model call when an ingredient the dish is named after is unavailable; otherwise the model
rewrites the recipe and the checks in revision_check.py reject any result that breaks a rule; a
rejected answer gets one more call with the check's message. An answer that drops a main ingredient
without an owned replacement is returned as a refusal; any other broken answer is a failure and is
never repaired silently. Measured in research/experiments/dish_revision (rounds 2 and 3)."""

import logging

from app.dishes.errors import MODEL_NOT_CONFIGURED, DishLLMError
from app.dishes.korean import attach
from app.dishes.prompts import ModelRequest, reask_request, revise_request
from app.dishes.revision_check import (
    RefusalNeeded,
    Violation,
    check,
    check_main_kept,
    check_short_mentions,
    identity_missing,
)
from app.dishes.roles import Availability, ChatModel, DishCatalog, RecipeBook
from app.dishes.schemas import (
    RecipeView,
    RevisedIngredient,
    RevisedRecipe,
    ReviseResponse,
    RevisionError,
    SourceRecipe,
)

log = logging.getLogger(__name__)


class Reviser:
    def __init__(
        self,
        catalog: DishCatalog,
        index: Availability,
        llm: ChatModel | None,
        recipes: RecipeBook,
    ):
        self.catalog, self.index, self.llm, self.recipes = catalog, index, llm, recipes

    def availability(self, recipe: SourceRecipe, ingredients: list[str]) -> list[str]:
        """owned / assumed / unavailable for each ingredient row of the recipe."""
        owned = self.index.owned(ingredients)
        return [self.index.status(row.name, owned) for row in recipe.ingredients]

    def view(self, dish_id: str, ingredients: list[str]) -> RecipeView | None:
        dish, recipe = self.catalog.get(dish_id), self.recipes.get(dish_id)
        if dish is None or recipe is None:
            return None
        return RecipeView(
            dish_id=dish_id,
            name=dish.name,
            recipe=recipe,
            availability=self.availability(recipe, ingredients),  # type: ignore[arg-type]
        )

    def revise(self, dish_id: str, ingredients: list[str]) -> ReviseResponse | None:
        """None when the dish or its recipe is unknown. Raises DishLLMError when the call fails."""
        view = self.view(dish_id, ingredients)
        if view is None:
            return None
        recipe, status = view.recipe, view.availability
        base = {"dish_id": dish_id, "original": recipe, "availability": status}
        if "unavailable" not in status:  # nothing to change: no model call
            same = RevisedRecipe(
                servings=recipe.servings,
                ingredients=[
                    RevisedIngredient(name=r.name, amount=r.amount) for r in recipe.ingredients
                ],
                steps=recipe.steps,
                tips=recipe.tips,
            )
            return ReviseResponse(status="revised", revised=same, **base)
        named = identity_missing(view.name, recipe, status)
        if named:  # the dish is named after something the user lacks: no model call
            log.info("dish revision: status=refused source=prescreen")
            reason = (
                f"요리 이름에 들어간 {attach(named[0], '이')} 없어서 이 요리로 바꾸기 어려워요."
            )
            return ReviseResponse(status="refused", refusal_reason=reason, **base)
        if self.llm is None:
            raise DishLLMError(MODEL_NOT_CONFIGURED)
        request = revise_request(recipe, view.name, status, ingredients)
        return self._answer(request, recipe, status, ingredients, base)

    def _answer(
        self,
        request: ModelRequest,
        recipe: SourceRecipe,
        status: list[str],
        ingredients: list[str],
        base: dict,
    ) -> ReviseResponse:
        """A checked answer. When the check rejects it, the model is asked once more with the
        check's message; the second answer is checked the same way and is never repaired."""
        data = self.llm.complete(request.system, request.user, request.name, request.schema)
        response, violation = self._judge(data, recipe, status, ingredients, base)
        if violation is None:
            return response
        log.info("dish revision: asking again after code=%s", violation.code)
        again = reask_request(request, violation.message)
        data = self.llm.complete(again.system, again.user, again.name, again.schema)
        return self._judge(data, recipe, status, ingredients, base)[0]

    def _judge(
        self,
        data: dict,
        recipe: SourceRecipe,
        status: list[str],
        ingredients: list[str],
        base: dict,
    ) -> tuple[ReviseResponse, Violation | None]:
        """The response for one answer, and the violation when the check rejected it."""
        if data.get("can_revise") is False:
            reason = data.get("refusal_reason")
            if isinstance(reason, str) and reason.strip():
                log.info("dish revision: status=refused")
                return ReviseResponse(status="refused", refusal_reason=reason.strip(), **base), None
            violation = Violation("incomplete", "A refusal needs a reason")
            return self._failed(base, violation), violation
        try:
            revised, changes = check(data, recipe, status, self.index, ingredients)
            check_main_kept(recipe, status, revised, changes)
            check_short_mentions(recipe, status, revised)
        except RefusalNeeded as needed:
            log.info("dish revision: status=refused source=check")
            return ReviseResponse(status="refused", refusal_reason=needed.reason, **base), None
        except Violation as violation:
            return self._failed(base, violation), violation
        log.info("dish revision: status=revised changes=%d", len(changes))
        return ReviseResponse(status="revised", revised=revised, changes=changes, **base), None

    @staticmethod
    def _failed(base: dict, violation: Violation) -> ReviseResponse:
        log.warning("dish revision: status=failed code=%s", violation.code)
        error = RevisionError(
            code=violation.code, message="바꾼 레시피가 규칙을 어겨서 보여 드릴 수 없어요."
        )
        return ReviseResponse(status="failed", error=error, **base)
