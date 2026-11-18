"""AI-assisted HE policy, 2026-11-10; human review pending.

Exact source dish names for manufacturing pantry products, not ready meals.
Never match substrings: 된장찌개 is still a supported meal. Source rows remain intact.
"""

from app.recipes.constants import normalize_name

MANUFACTURING_DISHES = frozenset({"된장", "고추장", "간장", "메주"})


def is_supported_recipe(name: str) -> bool:
    return normalize_name(name) not in MANUFACTURING_DISHES
