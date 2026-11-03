# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
"""Decisions that need no model call.

``prescreen_refusal`` refuses a recipe whose dish name contains an ingredient that is not available
(not in the inventory, not water, not an assumed seasoning). The prompt tells the model to refuse
in exactly this case, so the model call is saved, not a new rule introduced. The test is lexical
(an ingredient name of at least two characters occurs in the dish name); two spellings of the same
ingredient (``_SYNONYMS``) count as one, so an owned "달걀" satisfies a recipe row "계란".
"""

from collections.abc import Sequence

from .compact import _SYNONYMS, available_ids
from .models import InventoryIngredient, SourceRecipe
from .seasoning import ASSUME_ALL, SeasoningPolicy


def missing_identity_names(
    recipe: SourceRecipe,
    inventory: Sequence[InventoryIngredient],
    *,
    seasonings: SeasoningPolicy = ASSUME_ALL,
) -> list[str]:
    """Names of dish-name ingredients that are unavailable, in recipe order (empty: none)."""
    allowed = available_ids(recipe, inventory, seasonings=seasonings)
    have = {item.name for item in inventory}
    for row in recipe.ingredients:
        if row.ingredient_id in allowed:
            have.update(n for n in (row.name, row.original_name) if n)
    for group in _SYNONYMS:
        if have & group:
            have |= group
    missing: list[str] = []
    for row in recipe.ingredients:
        if row.ingredient_id in allowed:
            continue
        terms = [t for t in (row.name, row.original_name) if t and len(t) >= 2]
        if any(t in recipe.name for t in terms) and not any(t in have for t in terms):
            if row.name not in missing:
                missing.append(row.name)
    return missing


def prescreen_refusal(
    recipe: SourceRecipe,
    inventory: Sequence[InventoryIngredient],
    *,
    seasonings: SeasoningPolicy = ASSUME_ALL,
) -> dict | None:
    """A refusal in the public result shape, or None when the model should decide."""
    names = missing_identity_names(recipe, inventory, seasonings=seasonings)
    if not names:
        return None
    reason = f"요리 이름에 들어간 핵심 재료({', '.join(names)})가 없어 이 요리를 만들 수 없습니다."
    return {
        "can_revise": False,
        "reason": reason,
        "changes": [],
        "revised_recipe": None,
    }
