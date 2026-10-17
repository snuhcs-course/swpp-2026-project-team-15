"""Verify URL-free CSV imports without changing source files or existing databases."""
# AI-generated with Codex(6.1 Sol)
# 2026-10-17; reviewed by Soohyun An

import csv
import sqlite3
from contextlib import closing

import pytest

from db.import_recipes import TABLES, create_database


@pytest.fixture
def recipe_csvs(tmp_path):
    """Create all eight CSVs with repeated ingredient rows and nullable step tips."""
    directory = tmp_path / "csv"
    directory.mkdir()
    records = {
        "recipe": [{"recipe_id": 9, "name": "Fixture recipe", "servings": "4 servings"}],
        "ingredient": [{"ingredient_id": 32, "name": "Egg"}],
        "recipe_ingredient": [
            {"recipe_ingredient_id": index, "recipe_id": 9, "ingredient_id": 32,
             "quantity_text": quantity, "ingredient_type_code": "3060001"}
            for index, quantity in ((1, "2 eggs"), (2, "a pinch"))
        ],
        "recipe_step": [{"step_id": 1, "recipe_id": 9, "step_number": 1,
                         "instruction": "Cook thoroughly."}],
    }
    for spec in TABLES:
        with (directory / spec.filename).open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=spec.columns)
            writer.writeheader()
            writer.writerows(records.get(spec.table, []))
    return directory


def test_import_preserves_recipe_data_without_url_columns(recipe_csvs, tmp_path):
    before = {path.name: path.read_bytes() for path in recipe_csvs.iterdir()}
    database = tmp_path / "recipes.sqlite3"
    counts = create_database(recipe_csvs, database)
    assert counts["recipe"] == 1
    assert counts["recipe_step"] == 1
    assert counts["recipe_ingredient"] == 2
    with closing(sqlite3.connect(database)) as connection:
        recipe_columns = [row[1] for row in connection.execute("PRAGMA table_info(recipe)")]
        step_columns = [row[1] for row in connection.execute("PRAGMA table_info(recipe_step)")]
        assert recipe_columns == ["recipe_id", "name", "description", "cuisine_type", "category",
                                  "cooking_time", "calories", "servings", "difficulty"]
        assert step_columns == ["step_id", "recipe_id", "step_number", "instruction", "tip"]
        assert connection.execute("SELECT recipe_id,name,servings FROM recipe").fetchall() == [
            (9, "Fixture recipe", "4 servings")]
        assert connection.execute(
            "SELECT recipe_ingredient_id,ingredient_id,quantity_text "
            "FROM recipe_ingredient ORDER BY recipe_ingredient_id"
        ).fetchall() == [(1, 32, "2 eggs"), (2, 32, "a pinch")]
        assert connection.execute("SELECT tip FROM recipe_step").fetchone() == (None,)
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert {path.name: path.read_bytes() for path in recipe_csvs.iterdir()} == before


@pytest.mark.parametrize("filename,column", [
    ("Recipe.csv", "main_image_url"), ("Recipe.csv", "source_url"),
    ("RecipeStep.csv", "image_url"),
])
def test_obsolete_csv_headers_fail_before_database_creation(
    recipe_csvs, tmp_path, filename, column
):
    path = recipe_csvs / filename
    text = path.read_text(encoding="utf-8")
    header, rows = text.split("\n", 1)
    path.write_text(header + "," + column + "\n" + rows, encoding="utf-8")
    database = tmp_path / "recipes.sqlite3"
    with pytest.raises(ValueError, match="expected columns"):
        create_database(recipe_csvs, database)
    assert not database.exists()


def test_import_never_rebuilds_existing_database(recipe_csvs, tmp_path):
    database = tmp_path / "recipes.sqlite3"
    create_database(recipe_csvs, database)
    before = database.read_bytes()
    with pytest.raises(ValueError, match="refusing to overwrite"):
        create_database(recipe_csvs, database)
    assert database.read_bytes() == before
