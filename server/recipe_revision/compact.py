"""Compact revision input.

``build_compact_request`` sends only what the model needs to revise a recipe: ids, names, quantity
text, step text, non-null tips and servings. Fields the model does not use (description, calories,
difficulty, cuisine, category, cooking time, source type codes and labels, null values) are dropped.
The system prompt and the response schema are the unchanged ones from ``core``.
"""

import json

from .core import SYSTEM_PROMPT, RevisionRequest
from .models import InventoryIngredient, SourceRecipe


def build_compact_request(
    recipe: SourceRecipe, inventory: tuple[InventoryIngredient, ...]
) -> RevisionRequest:
    """Build the pruned request; row and step ids stay because the response refers to them."""
    rows = []
    for row in recipe.ingredients:
        entry = {
            "recipe_ingredient_id": row.recipe_ingredient_id,
            "ingredient_id": row.ingredient_id,
            "name": row.name,
        }
        if row.quantity_text:
            entry["quantity_text"] = row.quantity_text
        if row.original_name and row.original_name != row.name:
            entry["as_written"] = row.original_name
        rows.append(entry)
    steps = []
    for step in recipe.steps:
        entry = {
            "step_id": step.step_id,
            "step_number": step.step_number,
            "instruction": step.instruction,
        }
        if step.tip:
            entry["tip"] = step.tip
        steps.append(entry)
    original = {"name": recipe.name}
    if recipe.servings:
        original["servings"] = recipe.servings
    original["ingredients"] = rows
    original["steps"] = steps
    payload = {
        "original": original,
        "inventory": [
            {"ingredient_id": item.ingredient_id, "name": item.name} for item in inventory
        ],
    }
    user = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return RevisionRequest(SYSTEM_PROMPT, user)
