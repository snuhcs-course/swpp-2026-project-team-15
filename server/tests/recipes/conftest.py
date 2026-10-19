"""Independent integration fixtures; legacy recommendation fixtures stay unchanged."""
# AI-generated with Codex (GPT-6.1 Sol)
# 2026-10-17; reviewed by Soohyun An

import sqlite3

import pytest

from app.database import read_only_sqlite_engine
from app.recipes.service import RecipeRepository
from tests.conftest import SCHEMA


@pytest.fixture
def integration_db(tmp_path):
    """Six candidates plus recipes failing C, with source duplicates and missing items."""
    path = tmp_path / "integration.sqlite3"
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA.read_text(encoding="utf-8"))
        db.executemany(
            "INSERT INTO ingredient VALUES (?,?)",
            [
                (1, "Alpha"),
                (2, "Beta"),
                (3, "Gamma"),
                (4, "Salt"),
                (6, "Alias Alpha"),
                (204, "Water"),
            ],
        )
        definitions = {
            10: [(1, "3060001"), (3, "unknown")],
            20: [(1, "3060002"), (2, "3060002"), (1, "3060003")],
            30: [(1, "3060001")],
            40: [(1, "3060001")],
            50: [(1, "3060001"), (6, "3060002")],
            60: [(4, "3060003")],
            70: [(3, "3060001")],
            80: [(1, "3060002")],
            90: [(1, "3060001"), (3, "unknown")],
        }
        for recipe_id, ingredients in definitions.items():
            db.execute(
                "INSERT INTO recipe(recipe_id,name,description,servings) VALUES (?,?,?,?)",
                (recipe_id, f"Recipe {recipe_id}", "Source context", "4 servings"),
            )
            for ingredient_id, code in [*ingredients, (4, "3060003"), (204, "3060001")]:
                db.execute(
                    """INSERT INTO recipe_ingredient
                    (recipe_id,ingredient_id,quantity_text,ingredient_type_code,original_name)
                    VALUES (?,?,?,?,?)""",
                    (recipe_id, ingredient_id, None, code, "Raw label"),
                )
            for instruction, tip in (("First", None), ("Second", "Source tip")):
                db.execute(
                    """INSERT INTO recipe_step(recipe_id,step_number,instruction,tip)
                    VALUES (?,1,?,?)""",
                    (recipe_id, instruction, tip),
                )
    return path


@pytest.fixture
def integration_repository(integration_db):
    engine = read_only_sqlite_engine(integration_db)
    yield RecipeRepository(engine)
    engine.dispose()
