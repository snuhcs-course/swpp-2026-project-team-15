# AI-generated reviewed recipe normalization with Codex, 2026-11-15; reviewed by Soohyun An
"""Build traceable JSON documents in memory without publishing a catalog."""

from collections import Counter
from copy import deepcopy
from pathlib import Path

from recipe_ingredients.mapping import build_mapping


def build_documents(selected_path: Path, decisions_path: Path, catalog_path: Path) -> dict:
    """Return mapping, normalized recipes and validation report keyed by output filename.

    Each source occurrence is stored once, including excluded rows and combined
    quantities. Component source references point to that occurrence; quantities
    are never inferred from combined amounts, ingredient names or recipe prose.
    The caller owns serialization and subsequent backup/publication operations.
    """
    plan = build_mapping(selected_path, decisions_path, catalog_path)
    reviews = {row["name_raw"]: row for row in plan["reviewed"]["decisions"]}
    mappings = {row["name_raw"]: row for row in plan["mappings"]}
    catalog = {row["ingredient_id"]: row["name"] for row in plan["catalog"]}
    normalized = deepcopy(plan["selected"])
    # Avoid silently replacing input metadata with our provenance registry.
    if "source_occurrences" in normalized:
        raise ValueError("Selected input already contains source_occurrences")
    occurrences, excluded, splits, missing = [], [], [], []
    source_counts, output_counts = Counter(), Counter()
    retained, unknown_components = 0, 0
    for item in normalized["recipes"]:
        transformed = []
        for original in item["recipe"]["ingredients"]:
            name = original["name_raw"]
            mapping, review = mappings[name], reviews[name]
            disposition = mapping["decision"]
            source = dict(
                source_id=item["source_id"],
                group=original["group"],
                order=original["order"],
                occurrence_index=len(occurrences),
            )
            occurrence = dict(source=source, original=deepcopy(original), decision=disposition)
            occurrences.append(occurrence)
            source_counts[disposition] += 1
            if original.get("quantity_text") is None or original.get("quantity_text") == "":
                missing.append(deepcopy(source))
            if disposition in {"exclude_non_ingredient", "exclude_prepared_component"}:
                excluded.append(dict(**deepcopy(occurrence), review=deepcopy(review)))
                continue
            is_split = disposition == "split_existing"
            if is_split:
                splits.append(deepcopy(occurrence))
            else:
                retained += 1
            for index, target in enumerate(mapping["targets"], 1):
                row = deepcopy(original)
                row.update(
                    ingredient_id=target["ingredient_id"],
                    normalized_name=target["normalized_name"],
                    source=deepcopy(source),
                    component_index=index,
                )
                if is_split:
                    row["quantity_text"] = review["targets"][index - 1].get("quantity_text")
                    unknown_components += row["quantity_text"] is None
                transformed.append(row)
                output_counts[disposition] += 1
        item["recipe"]["ingredients"] = transformed
    normalized["source_occurrences"] = occurrences
    _validate(plan["selected"], normalized, mappings, reviews, catalog)
    mapping_document = dict(
        catalog=deepcopy(plan["catalog"]),
        input_hashes=deepcopy(plan["input_hashes"]),
        mappings=[
            dict(**deepcopy(row), review=deepcopy(reviews[row["name_raw"]]))
            for row in plan["mappings"]
        ],
    )
    report = dict(
        input_paths=dict(
            selected=str(selected_path.resolve()),
            decisions=str(decisions_path.resolve()),
            catalog=str(catalog_path.resolve()),
        ),
        input_hashes=deepcopy(plan["input_hashes"]),
        recipe_count=len(normalized["recipes"]),
        catalog_count=len(catalog),
        new_catalog_count=len(
            {
                t["ingredient_id"]
                for m in plan["mappings"]
                if m["decision"] == "new_requested"
                for t in m["targets"]
            }
        ),
        source_rows=len(occurrences),
        output_rows=sum(output_counts.values()),
        retained_source_rows=retained,
        split_source_rows=len(splits),
        excluded_source_rows=len(excluded),
        source_rows_by_decision=dict(source_counts),
        output_rows_by_decision=dict(output_counts),
        missing_source_quantities=missing,
        split_components_without_quantity=unknown_components,
        split_occurrences=splits,
        excluded_occurrences=excluded,
        inactive_raw_names=[m["name_raw"] for m in plan["mappings"] if not m["active_occurrences"]],
        unresolved_references=[],
        validation_passed=True,
        catalog_published=False,
        service_suitability_assessed=False,
        follow_up=[
            "presentation/allergen metadata",
            "ingredient classification",
            "recipe entity conversion",
            "recipe revision and missing quantities",
            "image deployment and database import",
        ],
    )
    report["existing_catalog_count"] = report["catalog_count"] - report["new_catalog_count"]
    return {
        "ingredient-mapping.json": mapping_document,
        "normalized-recipes.json": normalized,
        "validation-report.json": report,
    }


def _validate(
    selected: dict, normalized: dict, mappings: dict, reviews: dict, catalog: dict
) -> None:
    """Check source accounting, exact component contents and unchanged recipe metadata."""
    restored = deepcopy(normalized)
    occurrences = restored.pop("source_occurrences")
    cursor = 0
    for original_item, item in zip(selected["recipes"], restored["recipes"], strict=True):
        expected_rows = []
        for original in original_item["recipe"]["ingredients"]:
            occurrence = occurrences[cursor]
            source = dict(
                source_id=item["source_id"],
                group=original["group"],
                order=original["order"],
                occurrence_index=cursor,
            )
            mapping = mappings[original["name_raw"]]
            if occurrence != dict(source=source, original=original, decision=mapping["decision"]):
                raise ValueError(f"Source occurrence changed: {source}")
            for index, target in enumerate(mapping["targets"], 1):
                if catalog.get(target["ingredient_id"]) != target["normalized_name"]:
                    raise ValueError(f"Unregistered output identity: {source}")
                expected = dict(original, **target, source=source, component_index=index)
                if mapping["decision"] == "split_existing":
                    expected["quantity_text"] = reviews[original["name_raw"]]["targets"][
                        index - 1
                    ].get("quantity_text")
                expected_rows.append(expected)
            cursor += 1
        if item["recipe"]["ingredients"] != expected_rows:
            raise ValueError(f"Normalized rows do not account for source: {item['source_id']}")
        item["recipe"]["ingredients"] = deepcopy(original_item["recipe"]["ingredients"])
    if restored != selected or cursor != len(occurrences):
        raise ValueError("Recipe metadata or source accounting changed")
