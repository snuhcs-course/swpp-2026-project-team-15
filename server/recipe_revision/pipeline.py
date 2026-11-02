"""Steps around one revision call: a refusal decided in code before the call, one optional retry
after a rejected answer, and a completed change list.

The refusal and the completed change list are deterministic. The retry is a second model call and
is off unless asked for. Order: prescreen (no model call when it refuses) -> model call + check ->
on rejection, optionally one retry with feedback -> completed change list on a delivered revision.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace

from .changes import complete_changes
from .compact import build_compact_request, check_details, check_result, retry_request
from .core import LLM, RevisionOutcome, RevisionRequest, parse_response, revise
from .models import InventoryIngredient, SourceRecipe
from .prescreen import prescreen_refusal
from .seasoning import ASSUME_ALL, SeasoningPolicy


@dataclass(frozen=True)
class Steps:
    prescreen: bool = True
    retry: bool = False
    complete_changes: bool = True
    check: bool = True  # False: no post-check, so a retry never triggers
    seasonings: SeasoningPolicy = ASSUME_ALL
    build: Callable[..., RevisionRequest] | None = None  # default: build_compact_request


def _usage_sum(first: dict, second: dict) -> dict:
    a, b = first.get("usage") or {}, second.get("usage") or {}
    return {k: a.get(k, 0) + b.get(k, 0) for k in {*a, *b}}


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
    if outcome.status == "check_failed" and steps.retry:
        details = check_details(
            parse_response(outcome.raw_response), recipe, inventory, seasonings=seasonings
        )
        again = retry_request(outcome.request, details)
        second = revise(recipe, inventory, llm, build=lambda r, i: again, check=checker)
        meta = {**meta, "model_calls": 2, "retried": True}
        if "usage" in meta or "usage" in second.provider_metadata:
            meta["usage"] = _usage_sum(meta, second.provider_metadata)
        outcome = replace(second, provider_metadata=meta)
    else:
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
