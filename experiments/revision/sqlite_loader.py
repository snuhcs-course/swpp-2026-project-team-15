"""Read-only full recipe adapter; no source-row deduplication or inference."""
# AI-generated initial importer with Codex (GPT-6.1 Sol)
# 2026-10-14 to 2026-10-17; reviewed by Soohyun An

from pathlib import Path
import sqlite3
from contextlib import closing

from server.recipe_revision.models import (InventoryIngredient, SourceIngredient,
                                           SourceRecipe, SourceStep)
from .cases import INVENTORIES, RECIPES


class PreflightError(ValueError):
    """Source data cannot support the requested fixed matrix."""


def load_inputs(database: Path, *, recipe_pairs=RECIPES,
                inventory_pairs=INVENTORIES) -> tuple[dict[int, SourceRecipe], dict[str, tuple[InventoryIngredient, ...]]]:
    """Validate requested ID/name pairs and load full snapshots before any LLM call.

    Defaults preserve whole-matrix preflight. Runners supply only selected recipes
    and inventories, so unrelated missing records do not block a selected run.
    Separate queries prevent ingredient/step Cartesian duplication. Nullable text
    stays null and raw classifications are not interpreted as required ingredients.
    """
    if not database.is_file():
        raise PreflightError(f"SQLite database does not exist: {database}")
    try:
        with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN")
            recipes = {}
            for recipe_id, expected_name in recipe_pairs:
                row = connection.execute("SELECT * FROM recipe WHERE recipe_id = ?", (recipe_id,)).fetchone()
                if row is None or row["name"] != expected_name:
                    raise PreflightError(f"Recipe {recipe_id} missing or name differs from {expected_name}")
                ingredients = tuple(SourceIngredient(**dict(item)) for item in connection.execute("""
                    SELECT ri.recipe_ingredient_id, ri.ingredient_id, i.name,
                           ri.quantity_text, ri.ingredient_type_code, ri.ingredient_type, ri.original_name
                    FROM recipe_ingredient ri JOIN ingredient i ON i.ingredient_id = ri.ingredient_id
                    WHERE ri.recipe_id = ? ORDER BY ri.recipe_ingredient_id
                """, (recipe_id,)))
                source_count = connection.execute(
                    "SELECT count(*) FROM recipe_ingredient WHERE recipe_id = ?", (recipe_id,)).fetchone()[0]
                steps = tuple(SourceStep(**dict(item)) for item in connection.execute("""
                    SELECT step_id, step_number, instruction, image_url, tip FROM recipe_step
                    WHERE recipe_id = ? ORDER BY step_number, step_id
                """, (recipe_id,)))
                if not ingredients or len(ingredients) != source_count or not steps:
                    raise PreflightError(f"Recipe {recipe_id} has missing ingredients, names or steps")
                recipes[recipe_id] = SourceRecipe(**dict(row), ingredients=ingredients, steps=steps)
            inventories = {}
            for experiment, pairs in inventory_pairs.items():
                items = []
                for ingredient_id, expected_name in pairs:
                    row = connection.execute("SELECT name FROM ingredient WHERE ingredient_id = ?",
                                             (ingredient_id,)).fetchone()
                    if row is None or row["name"] != expected_name:
                        raise PreflightError(f"Inventory ingredient {ingredient_id} missing or differs from {expected_name}")
                    items.append(InventoryIngredient(ingredient_id, row["name"]))
                inventories[experiment] = tuple(items)
            return recipes, inventories
    except (sqlite3.Error, TypeError, KeyError, IndexError) as exc:
        raise PreflightError(f"SQLite schema or source data is invalid ({type(exc).__name__})") from exc
