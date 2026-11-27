# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Observe production Revision checks without replacing their decisions."""

import time
from collections.abc import Callable, Sequence

from app.dishes.revision import Reviser
from app.dishes.revision_check import Violation
from app.dishes.roles import Availability, ChatModel, DishCatalog, RecipeBook
from app.dishes.schemas import ReviseResponse, SourceRecipe

from .contract import CheckEvent


class TracedReviser(Reviser):
    """Retain check events for the current execution while delegating production policy."""

    def __init__(
        self,
        catalog: DishCatalog,
        index: Availability,
        llm: ChatModel | None,
        recipes: RecipeBook,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(catalog, index, llm, recipes, clock=clock)
        self.checks: list[CheckEvent] = []

    def revise(self, dish_id: str, ingredients: list[str]) -> ReviseResponse | None:
        """Start a fresh trace; no-call and failed-call paths have no check events."""
        self.checks.clear()
        return super().revise(dish_id, ingredients)

    def _judge(
        self,
        data: dict,
        recipe: SourceRecipe,
        status: Sequence[str],
        ingredients: list[str],
        base: dict,
    ) -> tuple[ReviseResponse, Violation | None]:
        """Copy the production check outcome and return its original objects unchanged."""
        response, violation = super()._judge(data, recipe, status, ingredients, base)
        phase = "initial" if not self.checks else "final"
        if violation is not None:
            event = CheckEvent(
                phase=phase,
                result="violation",
                code=violation.code,
                message=violation.message,
            )
        elif data.get("can_revise") is False:
            # Production accepts a valid model refusal before invoking static checks.
            event = CheckEvent(phase=phase, result="not_run", code=None, message=None)
        elif response.status == "refused":
            # Production consumes RefusalNeeded internally; a feasible model answer
            # returned as a refusal therefore identifies that check-owned outcome.
            event = CheckEvent(
                phase=phase,
                result="refusal_needed",
                code=None,
                message=response.refusal_reason,
            )
        else:
            event = CheckEvent(phase=phase, result="passed", code=None, message=None)
        self.checks.append(event)
        return response, violation
