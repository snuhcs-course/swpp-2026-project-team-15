"""Steps around one revision call: a refusal decided in code before the call and a completed
change list. Both are deterministic. Order: prescreen (no model call when it refuses) -> model call
+ check -> completed change list on a delivered revision.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace

from .changes import complete_changes
from .compact import build_compact_request, check_result
from .core import LLM, RevisionOutcome, RevisionRequest, revise
from .models import InventoryIngredient, SourceRecipe
from .prescreen import prescreen_refusal
from .seasoning import ASSUME_ALL, SeasoningPolicy


@dataclass(frozen=True)
class Steps:
    prescreen: bool = True
    complete_changes: bool = True
    check: bool = True  # False: no post-check, so a retry never triggers
    seasonings: SeasoningPolicy = ASSUME_ALL
    build: Callable[..., RevisionRequest] | None = None  # default: build_compact_request


def revise_with_steps(
    recipe: SourceRecipe,
    inventory: tuple[InventoryIngredient, ...],
    llm: LLM,
    steps: Steps,
) -> RevisionOutcome:
    seasonings = steps.seasonings
    inventory = tuple(inventory)
    builder = steps.build or build_compact_request

    def build(rec, inv):
        return builder(rec, inv, seasonings=seasonings)

    def check(result, rec, inv):
        return check_result(result, rec, inv, seasonings=seasonings)

    checker = check if steps.check else None
    if steps.prescreen:
        refusal = prescreen_refusal(recipe, inventory, seasonings=seasonings)
        if refusal is not None:
            return RevisionOutcome(
                "refused",
                build(recipe, inventory),
                None,
                refusal,
                None,
                {"model_calls": 0, "prescreen": True},
            )
    outcome = revise(recipe, inventory, llm, build=build, check=checker)
    meta = {**outcome.provider_metadata, "model_calls": 1}
    outcome = replace(outcome, provider_metadata=meta)
    if steps.complete_changes and outcome.status == "revised":
        completed, added = complete_changes(outcome.model_result, recipe)
        if added:
            outcome = replace(
                outcome,
                model_result=completed,
                provider_metadata={**outcome.provider_metadata, "changes_completed": added},
            )
    return outcome
