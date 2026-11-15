# AI-generated input validation and ID mapping with Codex, 2026-11-15; reviewed by Soohyun An
"""Validate reviewed local inputs and calculate service ingredient identities."""

import csv
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

DISPOSITIONS = {
    "reuse_existing",
    "new_requested",
    "split_existing",
    "excluded_recipe_only",
    "exclude_non_ingredient",
    "exclude_prepared_component",
    "hold",
    "unresolved",
}


def _name(value: object, context: str, limit: int | None = None) -> str:
    """Validate text without normalizing user-authored names."""
    if not isinstance(value, str) or not value.strip() or (limit and len(value) > limit):
        raise ValueError(f"Invalid name: {context}")
    return value


def _id(value: object, context: str) -> int:
    """Accept catalog strings or strict integer IDs, rejecting nonpositive IDs."""
    if type(value) is int and value > 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal() and int(value) > 0:
        return int(value)
    raise ValueError(f"Invalid ingredient ID: {context}")


def _catalog(content: bytes) -> list[dict]:
    """Read the fixed two-column catalog and preserve its existing row order."""
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig"), newline=""))
    if reader.fieldnames != ["ingredient_id", "name"]:
        raise ValueError("Expected catalog columns: ingredient_id,name")
    rows, ids, names = [], set(), set()
    for record in reader:
        if None in record or any(v is None for v in record.values()):
            raise ValueError("Malformed catalog row")
        ingredient_id = _id(record["ingredient_id"], "catalog")
        name = _name(record["name"], "catalog", 100)
        if ingredient_id in ids or name in names:
            raise ValueError(f"Duplicate catalog ID or name: {ingredient_id} {name}")
        ids.add(ingredient_id)
        names.add(name)
        rows.append(dict(ingredient_id=ingredient_id, name=name))
    return rows


def _selection(selected: dict) -> tuple[Counter, Counter, dict]:
    """Count raw occurrences and recipes while validating source-row identities."""
    if not isinstance(selected, dict) or not isinstance(selected.get("recipes"), list):
        raise ValueError("Expected selected recipes array")
    occurrences, recipe_counts, examples = Counter(), Counter(), {}
    recipe_ids = set()
    for item in selected["recipes"]:
        if not isinstance(item, dict) or not isinstance(item.get("recipe"), dict):
            raise ValueError("Invalid selected recipe")
        source_id = _name(item.get("source_id"), "source_id")
        recipe = item["recipe"]
        source = recipe.get("source")
        if not isinstance(source, dict) or source.get("id") != source_id or source_id in recipe_ids:
            raise ValueError(f"Invalid or duplicate source identity: {source_id}")
        recipe_ids.add(source_id)
        ingredients = recipe.get("ingredients")
        if not isinstance(ingredients, list):
            raise ValueError(f"Expected ingredients: {source_id}")
        identities, names = set(), set()
        for row in ingredients:
            if not isinstance(row, dict):
                raise ValueError(f"Invalid ingredient row: {source_id}")
            name = _name(row.get("name_raw"), source_id)
            order, group = row.get("order"), row.get("group")
            if type(order) is not int or order <= 0 or not isinstance(group, str):
                raise ValueError(f"Invalid ingredient group/order: {source_id} {name}")
            identity = (group, order)
            if identity in identities:
                raise ValueError(f"Duplicate ingredient group/order: {source_id} {name}")
            identities.add(identity)
            occurrences[name] += 1
            names.add(name)
            examples.setdefault(name, source_id)
        recipe_counts.update(names)
    return occurrences, recipe_counts, examples


def _target(record: dict, catalog: dict, context: str) -> dict:
    """Resolve a reviewed reuse target without changing its catalog identity."""
    if not isinstance(record, dict):
        raise ValueError(f"Invalid target: {context}")
    ingredient_id = _id(record.get("ingredient_id"), context)
    name = _name(record.get("normalized_name"), context, 100)
    if catalog.get(ingredient_id) != name:
        raise ValueError(f"Unknown ID/name pair: {context} {ingredient_id} {name}")
    return dict(ingredient_id=ingredient_id, normalized_name=name)


def build_mapping(selected_path: Path, decisions_path: Path, catalog_path: Path) -> dict:
    """Return a read-only ID plan from selected recipes, reviewed JSON and Ingredient.csv.

    Existing IDs and row order are retained. Active approved canonical names receive
    consecutive IDs above the catalog maximum in Python string sort order. Unused
    historical decisions are retained without allocating new IDs. Nothing is written.
    """
    contents = {
        "selected": selected_path.read_bytes(),
        "decisions": decisions_path.read_bytes(),
        "catalog": catalog_path.read_bytes(),
    }
    hashes = {key: hashlib.sha256(value).hexdigest() for key, value in contents.items()}
    selected = json.loads(contents["selected"].decode("utf-8-sig"))
    reviewed = json.loads(contents["decisions"].decode("utf-8-sig"))
    existing = _catalog(contents["catalog"])
    by_id = {row["ingredient_id"]: row["name"] for row in existing}
    existing_names = set(by_id.values())
    occurrences, recipe_counts, examples = _selection(selected)
    if not isinstance(reviewed, dict) or not isinstance(reviewed.get("decisions"), list):
        raise ValueError("Expected reviewed decisions array")
    metadata = reviewed.get("active_selection", {})
    if not isinstance(metadata, dict):
        raise ValueError("Invalid active_selection metadata")
    if "sha256" in metadata and metadata["sha256"] != hashes["selected"]:
        raise ValueError("Selected dataset SHA256 mismatch")
    expected_counts = dict(
        recipe_count=len(selected["recipes"]),
        ingredient_rows=sum(occurrences.values()),
        unique_raw_names=len(occurrences),
    )
    for key, expected in expected_counts.items():
        if key in metadata and (type(metadata[key]) is not int or metadata[key] != expected):
            raise ValueError(f"Inconsistent active_selection {key}")
    indexed, targets, new_names = {}, {}, set()
    for row in reviewed["decisions"]:
        if not isinstance(row, dict):
            raise ValueError("Invalid decision row")
        name = _name(row.get("name_raw"), "decision")
        if name in indexed:
            raise ValueError(f"Duplicate decision: {name}")
        indexed[name] = row
        disposition = row.get("decision")
        context = f"{name} (recipe {examples.get(name, 'inactive')})"
        if not isinstance(disposition, str) or disposition not in DISPOSITIONS:
            raise ValueError(f"Unknown disposition: {context}")
        for key, count in [
            ("active_occurrences", occurrences[name]),
            ("active_recipe_count", recipe_counts[name]),
        ]:
            if key in row and (type(row[key]) is not int or row[key] != count):
                raise ValueError(f"Inconsistent {key}: {context}")
        if occurrences[name] and disposition in {"hold", "unresolved", "excluded_recipe_only"}:
            raise ValueError(f"Unresolved or quality-excluded active ingredient: {context}")
        targets[name] = []
        if disposition == "reuse_existing":
            targets[name] = [_target(row, by_id, context)]
        elif disposition == "new_requested":
            canonical = _name(row.get("normalized_name"), context, 100)
            if row.get("ingredient_id") is not None or canonical in existing_names:
                raise ValueError(f"New name conflicts with catalog or assigned ID: {context}")
            if occurrences[name]:
                new_names.add(canonical)
        elif disposition == "split_existing":
            components = row.get("targets")
            if not isinstance(components, list) or len(components) < 2:
                raise ValueError(f"Expected multiple split targets: {context}")
            targets[name] = [_target(t, by_id, context) for t in components]
            if len({t["ingredient_id"] for t in targets[name]}) != len(components):
                raise ValueError(f"Duplicate split targets: {context}")
        if disposition not in {"reuse_existing", "new_requested"}:
            if row.get("ingredient_id") is not None:
                raise ValueError(f"Unexpected single ingredient ID: {context}")
    for name in occurrences.keys() - indexed.keys():
        raise ValueError(f"Missing decision: {name} (recipe {examples[name]})")
    if "counts" in reviewed and reviewed["counts"] != dict(
        Counter(row["decision"] for row in indexed.values())
    ):
        raise ValueError("Inconsistent decision counts")
    first_id = max(by_id, default=0) + 1
    allocated = {name: first_id + i for i, name in enumerate(sorted(new_names))}
    for name, row in indexed.items():
        if row["decision"] == "new_requested" and occurrences[name]:
            canonical = row["normalized_name"]
            targets[name] = [dict(ingredient_id=allocated[canonical], normalized_name=canonical)]
    return dict(
        catalog=existing + [dict(ingredient_id=i, name=name) for name, i in allocated.items()],
        mappings=[
            dict(
                name_raw=name,
                decision=indexed[name]["decision"],
                active_occurrences=occurrences[name],
                active_recipe_count=recipe_counts[name],
                targets=targets[name],
            )
            for name in sorted(indexed)
        ],
        selected=selected,
        reviewed=reviewed,
        input_hashes=hashes,
    )
