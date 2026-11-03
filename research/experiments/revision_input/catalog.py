# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""Read recipes and ingredient names from a local recipe database, read-only.

The database is private and never part of the repository; pass its path explicitly.
"""

import sqlite3
from pathlib import Path

from recipe_revision.models import InventoryIngredient, SourceIngredient, SourceRecipe, SourceStep

WATER_ID = 204
RECIPE_FIELDS = (
    "recipe_id",
    "name",
    "description",
    "cuisine_type",
    "category",
    "cooking_time",
    "calories",
    "servings",
    "difficulty",
)


def load_catalog(path: Path) -> tuple[dict[int, SourceRecipe], dict[int, str]]:
    """Return ({recipe_id: SourceRecipe}, {ingredient_id: name}) from a read-only connection."""
    con = sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        names = {r["ingredient_id"]: r["name"] for r in con.execute("SELECT * FROM ingredient")}
        ingredients: dict[int, list[SourceIngredient]] = {}
        for r in con.execute(
            "SELECT ri.recipe_ingredient_id, ri.recipe_id, ri.ingredient_id, i.name,"
            " ri.quantity_text, ri.ingredient_type_code, ri.ingredient_type, ri.original_name"
            " FROM recipe_ingredient ri JOIN ingredient i USING (ingredient_id)"
            " ORDER BY ri.recipe_ingredient_id"
        ):
            row = dict(r)
            ingredients.setdefault(row.pop("recipe_id"), []).append(SourceIngredient(**row))
        steps: dict[int, list[SourceStep]] = {}
        for r in con.execute("SELECT * FROM recipe_step ORDER BY step_number, step_id"):
            row = dict(r)
            row.pop("image_url", None)
            steps.setdefault(row.pop("recipe_id"), []).append(SourceStep(**row))
        recipes = {}
        for r in con.execute("SELECT * FROM recipe ORDER BY recipe_id"):
            fields = {k: r[k] for k in RECIPE_FIELDS if k in r.keys()}
            rid = fields["recipe_id"]
            recipes[rid] = SourceRecipe(
                **fields,
                ingredients=tuple(ingredients.get(rid, ())),
                steps=tuple(steps.get(rid, ())),
            )
    finally:
        con.close()
    return recipes, names


def inventory_for(case: dict, names: dict[int, str]) -> tuple[InventoryIngredient, ...]:
    """The case pantry; water is appended as the server does."""
    ids = list(dict.fromkeys([*case["inventory_ids"], WATER_ID]))
    return tuple(InventoryIngredient(i, names[i]) for i in ids)
