# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
"""Deterministic stand-in for the model, for offline plumbing checks only.

It is a labelled mock: it makes no network call and its answers say nothing about model quality.
Rules: refuse when an ingredient named in the dish name is unavailable; otherwise return the
source recipe without the unavailable ingredients and with the steps unchanged. Unchanged steps
keep the names of removed ingredients, so the post-check rejects some answers and the rejection
and retry paths run. Token counts are rough character-based estimates.
"""

import json
import math

from recipe_revision.core import LLMResponse, RevisionRequest

from . import checkers as ck


class OfflineLLM:
    """Call ``prepare`` with the case before each ``generate``."""

    def __init__(self):
        self._recipe = None
        self._allowed: set[int] = set()
        self.calls = 0

    def configuration(self) -> dict:
        return {"provider": "mock", "model": "offline-rule-v1", "is_mock": True}

    def prepare(self, recipe, allowed_ids: set[int]) -> None:
        self._recipe, self._allowed = recipe, set(allowed_ids)

    def generate(self, request: RevisionRequest) -> LLMResponse:
        self.calls += 1
        recipe, allowed = self._recipe, self._allowed
        verdict, _ = ck.expected_verdict(recipe, allowed)
        usable = [r for r in recipe.ingredients if r.ingredient_id in allowed | {ck.WATER_ID}]
        if verdict == "refuse" or not usable:
            result = {
                "can_revise": False,
                "reason": "MOCK: an ingredient named in the dish name is unavailable.",
                "changes": [],
                "revised_recipe": None,
            }
        else:
            kept, dropped = {}, []
            for row in recipe.ingredients:
                if row.ingredient_id in allowed or row.ingredient_id == ck.WATER_ID:
                    kept.setdefault(
                        row.ingredient_id,
                        {
                            "ingredient_id": row.ingredient_id,
                            "name": row.name,
                            "quantity_text": row.quantity_text,
                        },
                    )
                else:
                    dropped.append(row)
            result = {
                "can_revise": True,
                "reason": "MOCK: unavailable ingredients omitted.",
                "changes": [
                    {
                        "kind": "omission",
                        "reason": f"MOCK: {row.name} is not available.",
                        "source_ingredient_row_ids": [row.recipe_ingredient_id],
                        "source_step_ids": [],
                    }
                    for row in dropped
                ],
                "revised_recipe": {
                    "name": recipe.name,
                    "servings": recipe.servings,
                    "ingredients": list(kept.values()),
                    "steps": [
                        {"step_number": s.step_number, "instruction": s.instruction, "tip": s.tip}
                        for s in recipe.steps
                    ],
                },
            }
        text = json.dumps({"result": result}, ensure_ascii=False)
        usage = {
            "prompt_tokens": math.ceil((len(request.system) + len(request.user)) / 3),
            "completion_tokens": math.ceil(len(text) / 3),
        }
        return LLMResponse(text, {"usage": usage})
