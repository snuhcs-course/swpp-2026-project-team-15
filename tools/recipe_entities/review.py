# AI-generated with Codex, 2026-11-16; reviewed by Soohyun An
"""Export occurrence-level role worksheets and validate human decisions."""

import csv
import hashlib
import io
import json
from pathlib import Path

ROLE_LABELS = {"3060001": "주재료", "3060002": "부재료", "3060003": "양념"}
CONTEXT_COLUMNS = [
    "recipe_id",
    "recipe_title",
    "source_group",
    "source_order",
    "source_occurrence_index",
    "component_index",
    "ingredient_id",
    "normalized_name",
    "original_name",
    "quantity_text",
]
HEADERS = [*CONTEXT_COLUMNS, "ingredient_type_code", "review_note"]
EXCLUDED = {"exclude_non_ingredient", "exclude_prepared_component"}


def _positive(value):
    return type(value) is int and value > 0


def _fail(identity, detail):
    raise ValueError(f"Recipe {identity}: {detail}")


def _key(row):
    return (row["recipe_id"], row["source_occurrence_index"], row["component_index"])


def _csv(content, headers, label):
    """Reject malformed rows before their partial values can enter a worksheet."""
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
    if reader.fieldnames != headers:
        raise ValueError(f"{label}: unexpected CSV header")
    rows = list(reader)
    if any(None in row or None in row.values() for row in rows):
        raise ValueError(f"{label}: malformed CSV row")
    return rows


def load_inputs(normalized_path: Path, catalog_path: Path):
    """Return validated normalized data, canonical worksheet rows and input hashes.

    Source occurrence indices address the preserved registry, including exclusions.
    Repeated ingredient IDs and split components remain distinct occurrences.
    """
    contents = {
        "normalized_recipes": normalized_path.read_bytes(),
        "ingredient_catalog": catalog_path.read_bytes(),
    }
    hashes = {name: hashlib.sha256(content).hexdigest() for name, content in contents.items()}
    catalog = {}
    names = set()
    for row in _csv(contents["ingredient_catalog"], ["ingredient_id", "name"], "catalog"):
        identity, name = row["ingredient_id"], row["name"]
        if not identity.isascii() or not identity.isdecimal() or int(identity) <= 0:
            raise ValueError(f"Invalid catalog ID: {identity}")
        if int(identity) in catalog or not name.strip() or name in names:
            raise ValueError(f"Duplicate or invalid catalog identity: {identity} / {name}")
        catalog[int(identity)] = name
        names.add(name)
    document = json.loads(contents["normalized_recipes"])
    if not isinstance(document, dict) or not isinstance(document.get("source_run_id"), str):
        raise ValueError("Invalid normalized recipe document")
    recipes, sources = document.get("recipes"), document.get("source_occurrences")
    if not isinstance(recipes, list) or not recipes or not isinstance(sources, list):
        raise ValueError("Recipes and source_occurrences must be lists; recipes cannot be empty")
    source_keys = set()
    for index, entry in enumerate(sources):
        if not isinstance(entry, dict) or not isinstance(entry.get("source"), dict):
            raise ValueError(f"Invalid source occurrence {index}")
        source, original = entry["source"], entry.get("original")
        identity = source.get("source_id")
        if (
            not isinstance(original, dict)
            or source.get("occurrence_index") != index
            or type(source.get("occurrence_index")) is not int
            or source.get("group") != original.get("group")
            or source.get("order") != original.get("order")
            or not isinstance(original.get("group"), str)
            or not _positive(original.get("order"))
            or not isinstance(original.get("name_raw"), str)
            or not original["name_raw"].strip()
        ):
            _fail(identity, f"invalid preserved source occurrence {index}")
        source_key = (identity, source["group"], source["order"])
        if source_key in source_keys:
            _fail(identity, f"duplicate preserved source occurrence {index}")
        source_keys.add(source_key)
    rows, seen, recipe_ids, components = [], set(), set(), {}
    for item in recipes:
        if not isinstance(item, dict):
            raise ValueError("Invalid recipe record")
        identity, recipe = item.get("source_id"), item.get("recipe")
        if (
            not isinstance(identity, str)
            or not identity.isascii()
            or not identity.isdecimal()
            or str(int(identity)) != identity
            or int(identity) <= 0
            or identity in recipe_ids
        ):
            _fail(identity, "invalid or duplicate source ID")
        recipe_ids.add(identity)
        if (
            not isinstance(recipe, dict)
            or not isinstance(recipe.get("source"), dict)
            or recipe["source"].get("id") != identity
            or not isinstance(recipe.get("title"), str)
            or not recipe["title"].strip()
            or not isinstance(recipe.get("ingredients"), list)
            or not recipe["ingredients"]
        ):
            _fail(identity, "invalid recipe identity, title or ingredients")
        for ingredient in recipe["ingredients"]:
            if not isinstance(ingredient, dict) or not isinstance(ingredient.get("source"), dict):
                _fail(identity, "invalid ingredient occurrence")
            source = ingredient["source"]
            index = source.get("occurrence_index")
            component = ingredient.get("component_index")
            if (
                type(index) is not int
                or index < 0
                or index >= len(sources)
                or not _positive(component)
                or source.get("source_id") != identity
            ):
                _fail(identity, f"invalid occurrence reference {index}")
            entry = sources[index]
            original = entry["original"]
            if (
                entry["source"] != source
                or entry.get("decision") in EXCLUDED
                or any(
                    ingredient.get(name) != original.get(name)
                    for name in ["group", "order", "name_raw", "note_raw", "source_material_id"]
                )
            ):
                _fail(identity, f"source context mismatch at occurrence {index}")
            iid = ingredient.get("ingredient_id")
            if (
                not _positive(iid)
                or iid not in catalog
                or ingredient.get("normalized_name") != catalog[iid]
            ):
                _fail(identity, f"ingredient identity mismatch at occurrence {index}")
            quantity = ingredient.get("quantity_text")
            if quantity is not None and not isinstance(quantity, str):
                _fail(identity, f"invalid quantity at occurrence {index}")
            if entry.get("decision") == "split_existing":
                if quantity is not None:
                    _fail(
                        identity, f"unknown split quantity must remain NULL at occurrence {index}"
                    )
            elif component != 1 or quantity != original.get("quantity_text"):
                _fail(identity, f"source quantity/component mismatch at occurrence {index}")
            occurrence = (identity, index, component)
            if occurrence in seen:
                _fail(identity, f"duplicate component at occurrence {index}")
            seen.add(occurrence)
            components.setdefault(index, set()).add(component)
            rows.append(
                dict(
                    zip(
                        HEADERS,
                        [
                            identity,
                            recipe["title"],
                            source["group"],
                            str(source["order"]),
                            str(index),
                            str(component),
                            str(iid),
                            catalog[iid],
                            ingredient["name_raw"],
                            quantity or "",
                            "",
                            "",
                        ],
                        strict=True,
                    )
                )
            )
    for index, entry in enumerate(sources):
        identity = entry["source"]["source_id"]
        actual = components.get(index, set())
        if identity not in recipe_ids:
            _fail(identity, f"source occurrence {index} belongs to an unknown recipe")
        if entry.get("decision") in EXCLUDED:
            if actual:
                _fail(identity, f"excluded occurrence {index} was restored")
        elif entry.get("decision") == "split_existing":
            if len(actual) < 2 or actual != set(range(1, len(actual) + 1)):
                _fail(identity, f"missing split component at occurrence {index}")
        elif actual != {1}:
            _fail(identity, f"missing source occurrence {index}")
    return document, rows, hashes


def create_review(normalized_path: Path, catalog_path: Path, output: Path) -> None:
    """Create an unclassified worksheet in a new directory without changing inputs."""
    if output.exists():
        raise ValueError(f"Review output already exists: {output}")
    document, rows, hashes = load_inputs(normalized_path, catalog_path)
    context = dict(
        version="entity-role-review-v1",
        input_hashes=hashes,
        headers=HEADERS,
        source_run_id=document["source_run_id"],
        row_keys=[list(_key(row)) for row in rows],
    )
    output.mkdir(parents=True, exist_ok=False)
    with (output / "ingredient-roles.csv").open("x", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    (output / "review-context.json").write_text(
        json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def read_review(normalized_path: Path, catalog_path: Path, review_dir: Path) -> list[dict]:
    """Return complete human decisions in source order; reject stale or edited context."""
    _, expected, hashes = load_inputs(normalized_path, catalog_path)
    context = json.loads((review_dir / "review-context.json").read_bytes())
    if context.get("input_hashes") != hashes:
        raise ValueError("Review input hash mismatch; use the reviewed input snapshot")
    keys = [list(_key(row)) for row in expected]
    if (
        context.get("version") != "entity-role-review-v1"
        or context.get("headers") != HEADERS
        or context.get("row_keys") != keys
    ):
        raise ValueError("Review worksheet context mismatch")
    rows = _csv((review_dir / "ingredient-roles.csv").read_bytes(), HEADERS, "review")
    expected_by_key = {_key(row): row for row in expected}
    approved = {}
    for row in rows:
        identity = row["recipe_id"]
        key = _key(row)
        if key not in expected_by_key or key in approved:
            _fail(identity, f"unknown or duplicate review occurrence {key}")
        if any(row[name] != expected_by_key[key][name] for name in CONTEXT_COLUMNS):
            _fail(identity, f"read-only review context changed at {key}")
        if row["ingredient_type_code"] not in ROLE_LABELS:
            _fail(identity, f"unclassified or invalid role at {key}")
        approved[key] = row
    missing = expected_by_key.keys() - approved.keys()
    if missing:
        raise ValueError(f"Missing review occurrences: {sorted(missing)}")
    return [approved[_key(row)] for row in expected]
