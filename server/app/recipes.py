# AI-generated with Claude Code (Opus 5.5), 2026-10-11; review pending by Jaehyuk Choi.
"""Read-only access to the recipe database built by server/db/import_recipes.py."""

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from app.schemas import RecipeRecommendation
from app.vocabulary import STAPLE_SEASONINGS, with_synonyms

# A recipe qualifies when it uses at least one non-staple fridge ingredient (staples alone
# do not make a meal) and lacks at most :max_missing ingredients beyond fridge and staples.
_RECOMMEND_SQL = """
WITH
  fridge AS (
    SELECT ingredient_id FROM ingredient WHERE name IN (SELECT value FROM json_each(:fridge))
  ),
  available AS (
    SELECT ingredient_id FROM fridge
    UNION
    SELECT ingredient_id FROM ingredient WHERE name IN (SELECT value FROM json_each(:staples))
  ),
  needs AS (SELECT DISTINCT recipe_id, ingredient_id FROM recipe_ingredient)
SELECT
  needs.recipe_id,
  SUM(needs.ingredient_id NOT IN (SELECT ingredient_id FROM available)) AS missing_count,
  SUM(needs.ingredient_id IN (SELECT ingredient_id FROM fridge)) AS fridge_count
FROM needs
GROUP BY needs.recipe_id
HAVING fridge_count >= 1 AND missing_count <= :max_missing
ORDER BY missing_count, fridge_count DESC, needs.recipe_id
LIMIT :limit
"""

_LEADING_NUMBER = re.compile(r"\d+")


def _leading_int(text: str | None) -> int | None:
    match = _LEADING_NUMBER.match(text or "")
    return int(match.group()) if match else None


class RecipeRepository:
    def __init__(self, db_path: Path) -> None:
        if not db_path.is_file():
            raise FileNotFoundError(f"Recipe database not found: {db_path}")
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(f"file:{self._db_path}?mode=ro", uri=True)

    def recommend(
        self, fridge: list[str], max_missing: int, limit: int
    ) -> list[RecipeRecommendation]:
        fridge_names = with_synonyms(fridge) - set(STAPLE_SEASONINGS)
        available_names = fridge_names | set(STAPLE_SEASONINGS)
        params = {
            "fridge": json.dumps(sorted(fridge_names), ensure_ascii=False),
            "staples": json.dumps(STAPLE_SEASONINGS, ensure_ascii=False),
            "max_missing": max_missing,
            "limit": limit,
        }
        with closing(self._connect()) as connection:
            recipe_ids = [row[0] for row in connection.execute(_RECOMMEND_SQL, params)]
            return [self._load(connection, recipe_id, available_names) for recipe_id in recipe_ids]

    @staticmethod
    def _load(
        connection: sqlite3.Connection, recipe_id: int, available_names: set[str]
    ) -> RecipeRecommendation:
        name, cooking_time, servings = connection.execute(
            "SELECT name, cooking_time, servings FROM recipe WHERE recipe_id = ?", (recipe_id,)
        ).fetchone()
        ingredients = [
            row[0]
            for row in connection.execute(
                """
                SELECT ingredient.name FROM recipe_ingredient
                JOIN ingredient USING (ingredient_id)
                WHERE recipe_id = ?
                GROUP BY ingredient_id
                ORDER BY MIN(recipe_ingredient_id)
                """,
                (recipe_id,),
            )
        ]
        steps = [
            row[0]
            for row in connection.execute(
                "SELECT instruction FROM recipe_step WHERE recipe_id = ? ORDER BY step_number",
                (recipe_id,),
            )
        ]
        return RecipeRecommendation(
            id=recipe_id,
            name=name,
            time_minutes=_leading_int(cooking_time),
            servings=_leading_int(servings),
            ingredients=ingredients,
            steps=steps,
            missing=[item for item in ingredients if item not in available_names],
        )
