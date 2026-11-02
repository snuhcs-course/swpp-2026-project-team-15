"""Completing the change list of a revised recipe."""

import copy

from .models import SourceRecipe


def complete_changes(result: dict, recipe: SourceRecipe) -> tuple[dict, int]:
    """Return (result with the change list completed, number of entries added).

    Adds an ``omission`` entry for each source ingredient that the revision removed but no change
    entry points at, so the change list explains every removal.
    """
    if not result.get("can_revise") or not result.get("revised_recipe"):
        return result, 0
    kept = {item["ingredient_id"] for item in result["revised_recipe"]["ingredients"]}
    row_ids: dict[int, list[int]] = {}
    names: dict[int, str] = {}
    for row in recipe.ingredients:
        row_ids.setdefault(row.ingredient_id, []).append(row.recipe_ingredient_id)
        names.setdefault(row.ingredient_id, row.name)
    referenced = {x for change in result["changes"] for x in change["source_ingredient_row_ids"]}
    added = []
    for ingredient_id, rows in row_ids.items():
        if ingredient_id in kept or referenced & set(rows):
            continue
        added.append(
            {
                "kind": "omission",
                "reason": f"레시피에서 제외된 재료: {names[ingredient_id]}",
                "source_ingredient_row_ids": rows,
                "source_step_ids": [],
            }
        )
    if not added:
        return result, 0
    out = copy.deepcopy(result)
    out["changes"] = [*out["changes"], *added]
    return out, len(added)
