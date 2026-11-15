# AI-generated with Codex, 2026-11-16; reviewed by Soohyun An
"""Build a new local bundle and record completion only after independent DB checks."""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from collections import Counter
from contextlib import closing
from pathlib import Path

from .entities import COLUMNS, _write_files, prepare_entities, read_entity, validate_output

IMPORTER = Path(__file__).resolve().parents[2] / "server/db/import_recipes.py"
TABLES = {
    "Recipe.csv": "recipe",
    "Ingredient.csv": "ingredient",
    "CookingTool.csv": "cooking_tool",
    "Allergen.csv": "allergen",
    "RecipeStep.csv": "recipe_step",
    "RecipeIngredient.csv": "recipe_ingredient",
    "RecipeCookingTool.csv": "recipe_cooking_tool",
    "IngredientAllergen.csv": "ingredient_allergen",
}


def _hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _values(row, columns):
    """Match the existing importer's blank-cell-to-NULL semantics without rewriting text."""
    return tuple(
        None if isinstance(row[c], str) and not row[c].strip() else row[c] for c in columns
    )


def _verify(plan: dict, output: Path) -> None:
    """Compare every CSV/DB field to the pre-write plan, including all existing rows."""
    for filename, columns in COLUMNS.items():
        actual = read_entity((output / "csv" / filename).read_bytes(), filename)
        expected = [_values(row, columns) for row in plan["tables"][filename]]
        if [_values(row, columns) for row in actual] != expected:
            raise ValueError(f"CSV values differ from plan: {filename}")
    for filename, content in plan["copied_files"].items():
        if (output / "csv" / filename).read_bytes() != content:
            raise ValueError(f"Copied CSV bytes changed: {filename}")
    if json.loads((output / "entity-provenance.json").read_bytes()) != plan["provenance"]:
        raise ValueError("Source provenance differs from plan")
    # Read-only mode also refuses a missing DB instead of creating an empty one.
    uri = (output / "recipes.sqlite3").resolve().as_uri() + "?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchall() != [("ok",)]:
            raise ValueError("SQLite integrity check failed")
        if db.execute("PRAGMA foreign_key_check").fetchall():
            raise ValueError("SQLite foreign-key violations")
        for filename, table in TABLES.items():
            columns = COLUMNS[filename]
            actual = db.execute(f"SELECT {','.join(columns)} FROM {table}").fetchall()
            expected = [_values(row, columns) for row in plan["tables"][filename]]
            if Counter(actual) != Counter(expected):
                raise ValueError(f"Database values differ from plan: {table}")


def build_entities(
    normalized: Path, catalog: Path, review: Path, existing_csv: Path, output: Path
) -> dict:
    """Create CSVs, provenance and a new verified DB without modifying supplied inputs.

    Failures report the phase and partial directory, which is retained for inspection.
    No retry, overwrite or repair of an existing result is performed.
    """
    phase, created = "preflight", False
    try:
        validate_output(review, existing_csv, output)
        plan = prepare_entities(normalized, catalog, review, existing_csv)
        schema = IMPORTER.with_name("schema.sql")
        paths = {
            "normalized_recipes": normalized,
            "ingredient_catalog": catalog,
            "importer": IMPORTER,
            "schema": schema,
        }
        paths.update({f"existing/{name}": existing_csv / name for name in COLUMNS})
        paths.update(
            {
                f"review/{name}": review / name
                for name in ["ingredient-roles.csv", "review-context.json"]
            }
        )
        hashes = {name: _hash(path) for name, path in paths.items()}
        if any(hashes[name] != digest for name, digest in plan["input_hashes"].items()):
            raise ValueError("Inputs changed during append preparation")
        output.mkdir(parents=True, exist_ok=False)
        created = True
        phase = "write"
        _write_files(plan, output)
        phase = "import"
        command = [
            sys.executable,
            str(IMPORTER),
            "--csv-dir",
            str(output / "csv"),
            "--db",
            str(output / "recipes.sqlite3"),
        ]
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=dict(os.environ, PYTHONIOENCODING="utf-8"),
        )
        if process.returncode:
            raise ValueError(f"Importer exited {process.returncode}: {process.stderr.strip()}")
        phase = "verify"
        _verify(plan, output)
        if any(_hash(path) != hashes[name] for name, path in paths.items()):
            raise ValueError("An input changed while building; discard this result")
        counts = {
            name: dict(
                existing=plan["existing_counts"][name],
                added=plan["total_counts"][name] - plan["existing_counts"][name],
                total=plan["total_counts"][name],
            )
            for name in COLUMNS
        }
        added_relations = [
            row
            for record in plan["provenance"]["recipes"]
            for row in record["ingredient_relations"]
        ]
        added_recipes = [row["source_record"]["recipe"] for row in plan["provenance"]["recipes"]]
        output_files = [
            *(f"csv/{name}" for name in COLUMNS),
            "entity-provenance.json",
            "recipes.sqlite3",
        ]
        report = dict(
            status="completed",
            input_paths={k: str(p.resolve()) for k, p in paths.items()},
            input_hashes=hashes,
            output_hashes={name: _hash(output / name) for name in output_files},
            counts=counts,
            importer_exit_code=process.returncode,
            database_fields_match=True,
            source_inputs_unchanged=True,
            foreign_key_violations=[],
            integrity_check="ok",
            provenance_file="entity-provenance.json",
            added_recipe_ids=[r["recipe_id"] for r in plan["provenance"]["recipes"]],
            missing_quantities=sum(
                not row["normalized_row"].get("quantity_text") for row in added_relations
            ),
            missing_metadata={
                field: sum(not row.get(field) for row in added_recipes)
                for field in [
                    "description",
                    "servings_text",
                    "cooking_time_text",
                    "difficulty_text",
                ]
            },
            service_suitability_assessed=False,
            deferred_work=[
                "image deployment",
                "app presentation and ingredient metadata",
                "service suitability and recommendation quality",
                "production import",
            ],
        )
        phase = "report"
        with (output / "validation-report.json").open("x", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        return report
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        sqlite3.Error,
        subprocess.SubprocessError,
    ) as exc:
        if created:
            failure = dict(
                status="failed",
                phase=phase,
                error=str(exc),
                output=str(output.resolve()),
                partial_paths=sorted(
                    str(p.relative_to(output)) for p in output.rglob("*") if p.is_file()
                ),
            )
            try:
                (output / "validation-report.json").write_text(
                    json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
            except OSError:
                pass  # The original disk error and output path remain available to the caller.
        raise ValueError(f"Build failed during {phase}; output={output}: {exc}") from exc
