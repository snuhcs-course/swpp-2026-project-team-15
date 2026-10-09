"""Create a local SQLite recipe database from the eight entity CSV files."""

from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CsvTable:
    filename: str
    table: str
    columns: tuple[str, ...]
    integer_columns: frozenset[str] = frozenset()
    max_lengths: tuple[tuple[str, int], ...] = ()


# Parent tables precede tables with foreign keys. CSV columns match the ER diagram.
TABLES = (
    CsvTable(
        "Recipe.csv",
        "recipe",
        (
            "recipe_id", "name", "description", "cuisine_type", "category",
            "cooking_time", "calories", "servings", "difficulty",
            "main_image_url", "source_url",
        ),
        frozenset({"recipe_id"}),
        (
            ("name", 100), ("cuisine_type", 50), ("category", 50),
            ("cooking_time", 20), ("calories", 20), ("servings", 20),
            ("difficulty", 50), ("main_image_url", 2048), ("source_url", 2048),
        ),
    ),
    CsvTable(
        "Ingredient.csv", "ingredient", ("ingredient_id", "name"),
        frozenset({"ingredient_id"}), (("name", 100),),
    ),
    CsvTable(
        "CookingTool.csv", "cooking_tool", ("tool_id", "name"),
        frozenset({"tool_id"}), (("name", 100),),
    ),
    CsvTable(
        "Allergen.csv", "allergen", ("allergen_id", "name"),
        frozenset({"allergen_id"}), (("name", 100),),
    ),
    CsvTable(
        "RecipeStep.csv",
        "recipe_step",
        ("step_id", "recipe_id", "step_number", "instruction", "image_url", "tip"),
        frozenset({"step_id", "recipe_id", "step_number"}),
        (("image_url", 2048),),
    ),
    CsvTable(
        "RecipeIngredient.csv",
        "recipe_ingredient",
        (
            "recipe_ingredient_id", "recipe_id", "ingredient_id", "quantity_text",
            "ingredient_type_code", "ingredient_type", "original_name",
        ),
        frozenset({"recipe_ingredient_id", "recipe_id", "ingredient_id"}),
        (
            ("quantity_text", 100), ("ingredient_type_code", 7),
            ("ingredient_type", 50), ("original_name", 255),
        ),
    ),
    CsvTable(
        "RecipeCookingTool.csv", "recipe_cooking_tool", ("recipe_id", "tool_id"),
        frozenset({"recipe_id", "tool_id"}),
    ),
    CsvTable(
        "IngredientAllergen.csv", "ingredient_allergen", ("ingredient_id", "allergen_id"),
        frozenset({"ingredient_id", "allergen_id"}),
    ),
)


def read_rows(csv_dir: Path, spec: CsvTable) -> list[tuple[int, tuple[object, ...]]]:
    path = csv_dir / spec.filename
    rows = []
    limits = dict(spec.max_lengths)

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != list(spec.columns):
            raise ValueError(
                f"{path}: expected columns {list(spec.columns)!r}; "
                f"found {reader.fieldnames!r}"
            )

        for record in reader:
            line = reader.line_num
            if None in record or any(value is None for value in record.values()):
                raise ValueError(f"{path}:{line}: malformed CSV row")

            values: list[object] = []
            for column in spec.columns:
                raw = record[column]
                value: object = None if not raw.strip() else raw
                if column in spec.integer_columns and value is not None:
                    try:
                        value = int(raw.strip())
                    except ValueError as exc:
                        raise ValueError(f"{path}:{line}: {column} must be an integer") from exc
                    if value <= 0:
                        raise ValueError(f"{path}:{line}: {column} must be positive")
                elif value is not None and column in limits and len(raw) > limits[column]:
                    raise ValueError(
                        f"{path}:{line}: {column} exceeds {limits[column]} characters"
                    )
                values.append(value)
            rows.append((line, tuple(values)))
    return rows


def create_database(csv_dir: Path, db_path: Path) -> dict[str, int]:
    if not csv_dir.is_dir():
        raise ValueError(f"CSV directory does not exist: {csv_dir}")
    if db_path.exists():
        raise ValueError(f"Database already exists; refusing to overwrite: {db_path}")

    # Validate every input before creating a database file.
    input_rows = [(spec, read_rows(csv_dir, spec)) for spec in TABLES]
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        if connection.execute("PRAGMA foreign_keys").fetchone()[0] != 1:
            raise RuntimeError("SQLite foreign-key enforcement could not be enabled")
        schema = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")
        connection.executescript(schema)

        counts = {}
        with connection:
            for spec, rows in input_rows:
                placeholders = ", ".join("?" for _ in spec.columns)
                columns = ", ".join(spec.columns)
                statement = f"INSERT INTO {spec.table} ({columns}) VALUES ({placeholders})"
                for line, values in rows:
                    try:
                        connection.execute(statement, values)
                    except sqlite3.IntegrityError as exc:
                        raise ValueError(f"{spec.filename}:{line}: {exc}") from exc
                counts[spec.table] = len(rows)

            violations = connection.execute("PRAGMA foreign_key_check").fetchall()
            if violations:
                raise ValueError(f"Foreign-key violations: {violations[:5]!r}")
        return counts
    except Exception:
        connection.close()
        db_path.unlink(missing_ok=True)
        raise
    finally:
        connection.close()


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    default_data_dir = repo_root / "data" / "recipes"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, default=default_data_dir)
    parser.add_argument("--db", type=Path, default=default_data_dir / "recipes.sqlite3")
    args = parser.parse_args()

    try:
        counts = create_database(args.csv_dir, args.db)
    except (OSError, sqlite3.Error, ValueError, RuntimeError) as exc:
        print(f"Import failed: {exc}", file=sys.stderr)
        return 1

    print(f"Created {args.db}")
    for table, count in counts.items():
        print(f"{table}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
