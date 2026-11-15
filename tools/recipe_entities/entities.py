# AI-generated with Codex, 2026-11-16; reviewed by Soohyun An
"""Append reviewed recipes to a separate CSV bundle with full source provenance."""

import csv
import hashlib
import io
import json
from pathlib import Path

from .review import ROLE_LABELS, load_review

# Mirror the stable entity contract; the existing importer remains the final DB check.
COLUMNS = {
    "Recipe.csv": [
        "recipe_id",
        "name",
        "description",
        "cuisine_type",
        "category",
        "cooking_time",
        "calories",
        "servings",
        "difficulty",
        "main_image_url",
    ],
    "Ingredient.csv": ["ingredient_id", "name"],
    "CookingTool.csv": ["tool_id", "name"],
    "Allergen.csv": ["allergen_id", "name"],
    "RecipeStep.csv": ["step_id", "recipe_id", "step_number", "instruction", "tip"],
    "RecipeIngredient.csv": [
        "recipe_ingredient_id",
        "recipe_id",
        "ingredient_id",
        "quantity_text",
        "ingredient_type_code",
        "ingredient_type",
        "original_name",
    ],
    "RecipeCookingTool.csv": ["recipe_id", "tool_id"],
    "IngredientAllergen.csv": ["ingredient_id", "allergen_id"],
}
APPENDED = {"Recipe.csv", "RecipeIngredient.csv", "RecipeStep.csv"}
LIMITS = {
    "name": 100,
    "cuisine_type": 50,
    "category": 50,
    "cooking_time": 20,
    "calories": 20,
    "servings": 20,
    "difficulty": 50,
    "main_image_url": 512,
    "quantity_text": 100,
    "ingredient_type_code": 7,
    "ingredient_type": 50,
    "original_name": 255,
}
REQUIRED_TEXT = {
    "Recipe.csv": ["name"],
    "Ingredient.csv": ["name"],
    "CookingTool.csv": ["name"],
    "Allergen.csv": ["name"],
    "RecipeStep.csv": ["instruction"],
    "RecipeIngredient.csv": ["ingredient_type_code"],
}


def _integer_column(column):
    return column.endswith("_id") or column == "step_number"


def read_entity(content: bytes, filename: str) -> list[dict]:
    """Read canonical fields, accepting the legacy recipe header without an image URL."""
    columns = COLUMNS[filename]
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
    allowed = [columns, columns[:-1]] if filename == "Recipe.csv" else [columns]
    if reader.fieldnames not in allowed:
        raise ValueError(f"{filename}: unexpected header")
    rows = []
    for row in reader:
        if None in row or None in row.values():
            raise ValueError(f"{filename}:{reader.line_num}: malformed CSV row")
        converted = {}
        for column in columns:
            value = row.get(column, "")
            if not value.strip():
                value = None
            elif _integer_column(column):
                try:
                    value = int(value)
                except ValueError as exc:
                    raise ValueError(f"{filename}: invalid integer in {column}") from exc
            converted[column] = value
        rows.append(converted)
    return rows


def _validate_tables(tables):
    """Refuse identity/relationship corruption before writing any output."""
    ids = {}
    for filename, rows in tables.items():
        columns = COLUMNS[filename]
        key_columns = (
            columns
            if filename in {"RecipeCookingTool.csv", "IngredientAllergen.csv"}
            else columns[:1]
        )
        seen = set()
        for row in rows:
            for column in columns:
                value = row[column]
                if _integer_column(column):
                    if type(value) is not int or not 0 < value <= 2**63 - 1:
                        raise ValueError(f"{filename}: invalid positive integer {column}: {value}")
                elif value is not None:
                    if not isinstance(value, str):
                        raise ValueError(f"{filename}: {column} must be text or NULL")
                    if column in LIMITS and len(value) > LIMITS[column]:
                        raise ValueError(
                            f"{filename}: {column} exceeds {LIMITS[column]} characters"
                        )
                if column in REQUIRED_TEXT.get(filename, ()) and (
                    value is None or not value.strip()
                ):
                    raise ValueError(f"{filename}: missing required {column}")
            key = tuple(row[column] for column in key_columns)
            if key in seen:
                raise ValueError(f"{filename}: duplicate identity {key}")
            seen.add(key)
        ids[filename] = {row[columns[0]] for row in rows}
    ingredient_names = [row["name"] for row in tables["Ingredient.csv"]]
    if len(set(ingredient_names)) != len(ingredient_names):
        raise ValueError("Ingredient.csv: duplicate ingredient names")
    references = {
        "RecipeStep.csv": [("recipe_id", "Recipe.csv")],
        "RecipeIngredient.csv": [("recipe_id", "Recipe.csv"), ("ingredient_id", "Ingredient.csv")],
        "RecipeCookingTool.csv": [("recipe_id", "Recipe.csv"), ("tool_id", "CookingTool.csv")],
        "IngredientAllergen.csv": [
            ("ingredient_id", "Ingredient.csv"),
            ("allergen_id", "Allergen.csv"),
        ],
    }
    for filename, columns in references.items():
        for row in tables[filename]:
            for column, parent in columns:
                if row[column] not in ids[parent]:
                    raise ValueError(f"{filename}: unresolved {column} {row[column]}")


def prepare_entities(normalized: Path, catalog: Path, review: Path, existing_csv: Path) -> dict:
    """Return a fully validated append plan without writing files or allocating DB IDs.

    New recipe IDs stay unchanged; relation/step IDs increase from existing maxima.
    The source record and occurrence registry retain details absent from DB columns.
    """
    document, decisions, input_hashes = load_review(normalized, catalog, review)
    contents = {name: (existing_csv / name).read_bytes() for name in COLUMNS}
    tables = {name: read_entity(content, name) for name, content in contents.items()}
    _validate_tables(tables)
    old_counts = {name: len(rows) for name, rows in tables.items()}
    catalog_bytes = catalog.read_bytes()
    current_catalog = read_entity(catalog_bytes, "Ingredient.csv")
    by_id = {row["ingredient_id"]: row["name"] for row in current_catalog}
    for row in tables["Ingredient.csv"]:
        if by_id.get(row["ingredient_id"]) != row["name"]:
            raise ValueError(f"Ingredient.csv: existing ID/name changed: {row['ingredient_id']}")
    tables["Ingredient.csv"] = current_catalog
    old_ids = {row["recipe_id"] for row in tables["Recipe.csv"]}
    collision = old_ids & {int(item["source_id"]) for item in document["recipes"]}
    if collision:
        raise ValueError(f"Recipe ID collision: {sorted(collision)}")
    approved = {
        (r["recipe_id"], int(r["source_occurrence_index"]), int(r["component_index"])): r
        for r in decisions
    }
    relation_id = max(
        (r["recipe_ingredient_id"] for r in tables["RecipeIngredient.csv"]), default=0
    )
    step_id = max((r["step_id"] for r in tables["RecipeStep.csv"]), default=0)
    provenance = dict(
        source_run_id=document["source_run_id"],
        recipes=[],
        source_occurrences=document["source_occurrences"],
    )
    for item in sorted(document["recipes"], key=lambda record: int(record["source_id"])):
        identity, recipe = item["source_id"], item["recipe"]
        rid = int(identity)
        tables["Recipe.csv"].append(
            dict(
                zip(
                    COLUMNS["Recipe.csv"],
                    [
                        rid,
                        recipe["title"],
                        recipe.get("description"),
                        None,
                        None,
                        recipe.get("cooking_time_text"),
                        None,
                        recipe.get("servings_text"),
                        recipe.get("difficulty_text"),
                        None,
                    ],
                    strict=True,
                )
            )
        )
        record = dict(recipe_id=rid, source_record=item, ingredient_relations=[], steps=[])
        for ingredient in recipe["ingredients"]:
            occurrence = (
                identity,
                ingredient["source"]["occurrence_index"],
                ingredient["component_index"],
            )
            decision = approved[occurrence]
            code = decision["ingredient_type_code"]
            relation_id += 1
            tables["RecipeIngredient.csv"].append(
                dict(
                    zip(
                        COLUMNS["RecipeIngredient.csv"],
                        [
                            relation_id,
                            rid,
                            ingredient["ingredient_id"],
                            ingredient.get("quantity_text"),
                            code,
                            ROLE_LABELS[code],
                            ingredient["name_raw"],
                        ],
                        strict=True,
                    )
                )
            )
            record["ingredient_relations"].append(
                dict(
                    recipe_ingredient_id=relation_id,
                    source=ingredient["source"],
                    component_index=ingredient["component_index"],
                    normalized_row=ingredient,
                    review=decision,
                )
            )
        steps = recipe.get("steps")
        if not isinstance(steps, list) or not steps:
            raise ValueError(f"Recipe {identity}: steps must be a nonempty list")
        orders = []
        for step in steps:
            if (
                not isinstance(step, dict)
                or type(step.get("order")) is not int
                or step["order"] <= 0
            ):
                raise ValueError(f"Recipe {identity}: invalid step order")
            orders.append(step["order"])
            tips = step.get("tips")
            if not isinstance(tips, list) or not all(isinstance(tip, str) for tip in tips):
                raise ValueError(f"Recipe {identity}: tips must be a list of text")
        if len(set(orders)) != len(orders):
            raise ValueError(f"Recipe {identity}: duplicate step order")
        for step in sorted(steps, key=lambda value: value["order"]):
            step_id += 1
            tables["RecipeStep.csv"].append(
                dict(
                    zip(
                        COLUMNS["RecipeStep.csv"],
                        [
                            step_id,
                            rid,
                            step["order"],
                            step.get("instruction"),
                            "\n".join(step["tips"]) or None,
                        ],
                        strict=True,
                    )
                )
            )
            record["steps"].append(dict(step_id=step_id, source_step=step))
        provenance["recipes"].append(record)
    _validate_tables(tables)
    input_hashes.update(
        {
            f"existing/{name}": hashlib.sha256(content).hexdigest()
            for name, content in contents.items()
        }
    )
    for name in ["ingredient-roles.csv", "review-context.json"]:
        input_hashes[f"review/{name}"] = hashlib.sha256((review / name).read_bytes()).hexdigest()
    return dict(
        tables=tables,
        provenance=provenance,
        copied_files={
            name: catalog_bytes if name == "Ingredient.csv" else content
            for name, content in contents.items()
            if name not in APPENDED
        },
        existing_counts=old_counts,
        total_counts={name: len(rows) for name, rows in tables.items()},
        input_hashes=input_hashes,
    )


def write_entities(
    normalized: Path, catalog: Path, review: Path, existing_csv: Path, output: Path
) -> dict:
    """Write CSV/provenance into a new directory; this alone is not DB-validated completion.

    Validation failures leave no output. I/O failures may leave a partial new
    directory for inspection; inputs and existing results are never overwritten.
    """
    if output.exists():
        raise ValueError(f"Entity output already exists: {output}")
    for directory in (existing_csv, review):
        if output.resolve().is_relative_to(directory.resolve()):
            raise ValueError(f"Unsafe input/output overlap: {output}")
    plan = prepare_entities(normalized, catalog, review, existing_csv)
    folder = output / "csv"
    output.mkdir(parents=True, exist_ok=False)
    folder.mkdir()
    for filename, columns in COLUMNS.items():
        path = folder / filename
        if filename in APPENDED:
            with path.open("x", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns)
                writer.writeheader()
                writer.writerows(plan["tables"][filename])
        else:
            with path.open("xb") as handle:
                handle.write(plan["copied_files"][filename])
    with (output / "entity-provenance.json").open("x", encoding="utf-8") as handle:
        json.dump(plan["provenance"], handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return {key: plan[key] for key in ("existing_counts", "total_counts", "input_hashes")}
