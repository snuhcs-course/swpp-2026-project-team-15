# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""The closed lists one suggestion answer may choose from. Pure functions, no model, no I/O.

``name`` is one of the dish names, ``have`` one of the user's own strings, and ``missing`` one of
the dish list's key ingredients that the user does not own (exact spelling, spaces ignored, or a
synonym group). Because an owned ingredient is not a choice for ``missing``, the model cannot list
it there. Unmatched forms (e.g. 다진마늘 for 마늘) are not mapped: asking the model to map them
merged different ingredients (두유 as 두부, 쪽파 as 대파) in
research/experiments/dish_output_formats (round 2).
"""

from collections.abc import Iterable
from dataclasses import dataclass

from app.dishes.catalog import Dish
from app.dishes.synonyms import SYNONYM_GROUPS


@dataclass(frozen=True)
class SuggestChoices:
    names: list[str]
    have: list[str]
    missing: list[str]


def _norm(text: str) -> str:
    return text.strip().replace(" ", "")


def ingredient_vocabulary(dishes: Iterable[Dish]) -> list[str]:
    """Distinct key ingredients, one spelling per synonym group (the most frequent one)."""
    counts: dict[str, int] = {}
    for dish in dishes:
        for key in dish.key_ingredients:
            counts[key] = counts.get(key, 0) + 1
    canonical: dict[str, str] = {}
    for group in SYNONYM_GROUPS:
        members = [m for m in group if m in counts]
        if members:
            best = min(members, key=lambda m: (-counts[m], m))
            canonical.update({m: best for m in group})
    return sorted({canonical.get(k, k) for k in counts})


def user_items(ingredients: list[str]) -> list[str]:
    """The user's strings, trimmed, without duplicates, in the given order."""
    return list(dict.fromkeys(i.strip() for i in ingredients if i and i.strip()))


def owned_vocabulary(items: list[str], vocabulary: list[str]) -> set[str]:
    """Vocabulary names the user owns by exact spelling (spaces ignored) or a synonym group."""
    forms = {_norm(i) for i in items}
    for group in SYNONYM_GROUPS:
        if forms & group:
            forms |= group
    return {v for v in vocabulary if v in forms}


def suggest_choices(
    ingredients: list[str], dish_names: list[str], vocabulary: list[str]
) -> SuggestChoices:
    items = user_items(ingredients)
    owned = owned_vocabulary(items, vocabulary)
    return SuggestChoices(
        names=list(dish_names), have=items, missing=[v for v in vocabulary if v not in owned]
    )
