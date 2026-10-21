"""Read-only SQLite adapter for the standalone recipe-filtering experiment.

This module owns local I/O and report formatting. Filtering definitions and
metrics live in ``server.recipe_filtering`` so the same logic can later be
called by a Django adapter without importing this experiment runner.
"""

# AI-generated initial implementation with Codex (GPT-6 Luna Medium),
# 2026-10-13; reviewed and revised by Soohyun An.

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from server.recipe_filtering.metrics import (  # noqa: E402
    MAIN,
    SECONDARY,
    SEASONING,
    Recipe,
    RecipeMetrics,
    _resolved_type,
    calculate_metrics,
)
from server.recipe_filtering.rules import Rule, build_rules, evaluate_rule  # noqa: E402


TYPE_CODES = {"3060001": MAIN, "3060002": SECONDARY, "3060003": SEASONING}
TYPE_ALIASES = {
    "주재료": MAIN, "main": MAIN,
    "부재료": SECONDARY, "secondary": SECONDARY,
    "양념": SEASONING, "seasoning": SEASONING,
}


def _type_name(name: object, code: object) -> str | None:
    """Map importer type labels/codes to the three metric categories.

    A recognized label takes precedence. If the label is blank, the importer
    code is used; unrecognized values remain unclassified rather than being
    guessed from an ingredient's name.
    """
    text = str(name).strip() if name is not None else ""
    if text:
        return TYPE_ALIASES.get(text.casefold(), TYPE_ALIASES.get(text))
    code_text = str(code).strip() if code is not None else ""
    return TYPE_CODES.get(code_text)


def load_recipes(connection: sqlite3.Connection) -> tuple[Recipe, ...]:
    """Adapt the SQLite importer schema to the pure filtering input model.

    The query is read-only and keeps recipes with no ingredient rows. Repeated
    relationship rows collapse to a normalized ID while their distinct source
    types are retained for conflict analysis. Normalized names are preserved
    for reporting, and original ingredient names for review and AI revision.
    """
    connection.row_factory = sqlite3.Row
    grouped: dict[int, dict[str, object]] = {}
    query = """
        SELECT r.recipe_id, r.name AS recipe_name,
               i.ingredient_id, i.name AS ingredient_name,
               ri.ingredient_type, ri.ingredient_type_code,
               ri.original_name
        FROM recipe AS r
        LEFT JOIN recipe_ingredient AS ri ON ri.recipe_id = r.recipe_id
        LEFT JOIN ingredient AS i ON i.ingredient_id = ri.ingredient_id
        ORDER BY r.recipe_id, i.ingredient_id, ri.recipe_ingredient_id
    """
    for row in connection.execute(query):
        recipe_id = int(row["recipe_id"])
        item = grouped.setdefault(
            recipe_id,
            {"name": row["recipe_name"], "types": defaultdict(set), "names": {}, "original_names": defaultdict(set)},
        )
        if row["ingredient_id"] is None:
            continue
        ingredient_id = int(row["ingredient_id"])
        item["types"].setdefault(ingredient_id, set())  # type: ignore[union-attr]
        kind = _type_name(row["ingredient_type"], row["ingredient_type_code"])
        if kind is not None:
            item["types"][ingredient_id].add(kind)  # type: ignore[index,union-attr]
        item["names"][ingredient_id] = row["ingredient_name"]  # type: ignore[index]
        original_name = row["original_name"]
        if original_name is not None:
            original_name = str(original_name).strip()
            if original_name:
                item["original_names"][ingredient_id].add(original_name)

    recipes = []
    for recipe_id, item in grouped.items():
        recipes.append(
            Recipe(
                recipe_id=recipe_id,
                name=str(item["name"]),
                ingredient_types={
                    ingredient_id: frozenset(types)
                    for ingredient_id, types in item["types"].items()  # type: ignore[union-attr]
                },
                ingredient_names=dict(item["names"]),  # type: ignore[arg-type]
                ingredient_original_names={
                    ingredient_id: tuple(sorted(names))
                    for ingredient_id, names in item["original_names"].items()
                }
            )
        )
    return tuple(recipes)


def load_semantic_annotations(path: Path | None) -> dict[int, tuple[str, str]]:
    """Load optional, explicit human-reviewed semantic labels by ingredient ID.

    The CSV must provide ``ingredient_id``, ``semantic_type``, and a nonempty
    ``reason``. These annotations are an analysis override only; no semantic
    label is inferred from source names or ingredient-type conflicts.
    """
    if path is None:
        return {}
    annotations: dict[int, tuple[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        expected = {"ingredient_id", "semantic_type", "reason"}
        if not expected.issubset(reader.fieldnames or []):
            raise ValueError(f"{path}: expected CSV columns {sorted(expected)}")
        for line, row in enumerate(reader, start=2):
            try:
                ingredient_id = int(row["ingredient_id"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path}:{line}: ingredient_id must be an integer") from exc
            semantic_type = TYPE_ALIASES.get((row["semantic_type"] or "").strip().casefold())
            reason = (row["reason"] or "").strip()
            if semantic_type is None or not reason:
                raise ValueError(f"{path}:{line}: semantic_type and reason are required")
            if ingredient_id in annotations:
                raise ValueError(f"{path}:{line}: duplicate ingredient_id {ingredient_id}")
            annotations[ingredient_id] = (semantic_type, reason)
    return annotations


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    """Write report rows as UTF-8-with-BOM CSV for spreadsheet compatibility."""
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _mean(values: Iterable[float | None]) -> float | None:
    """Average defined coverage values, excluding zero-denominator ``None``s."""
    filtered = [value for value in values if value is not None]
    return statistics.mean(filtered) if filtered else None


def _median(values: Iterable[float | None]) -> float | None:
    """Find the median of defined coverage values, excluding ``None``s."""
    filtered = [value for value in values if value is not None]
    return statistics.median(filtered) if filtered else None


def _metrics_row(metrics: RecipeMetrics) -> dict[str, object]:
    """Flatten a recipe's metrics into stable, human-readable report columns."""
    return {
        "recipe_id": metrics.recipe_id,
        "recipe_name": metrics.name,
        "total_ingredients": metrics.total_ingredients,
        "total_matches": metrics.total_matches,
        "total_coverage": metrics.total_coverage,
        "general_ingredients": metrics.general_ingredients,
        "general_matches": metrics.general_matches,
        "general_coverage": metrics.general_coverage,
        "main_ingredients": metrics.main_ingredients,
        "main_matches": metrics.main_matches,
        "main_coverage": metrics.main_coverage,
        "seasoning_ingredients": metrics.seasoning_ingredients,
        "seasoning_matches": metrics.seasoning_matches,
        "type_conflict_ids": ";".join(map(str, metrics.conflicting_ingredient_ids)),
        "main_seasoning_conflict_ids": ";".join(map(str, metrics.main_seasoning_conflict_ids)),
    }


def _ingredient_match_details(
    recipe: Recipe,
    available_ids: frozenset[int],
) -> tuple[list[int], list[int], list[int], list[int]]:
    """Return sorted available, missing, matched-main, and missing-main IDs."""
    recipe_ids = set(recipe.ingredient_types)
    main_ids = {
        ingredient_id
        for ingredient_id, types in recipe.ingredient_types.items()
        if _resolved_type(types) == MAIN
    }
    return (
        sorted(recipe_ids & available_ids),
        sorted(recipe_ids - available_ids),
        sorted(main_ids & available_ids),
        sorted(main_ids - available_ids),
    )


def _format_ingredients(recipe: Recipe, ingredient_ids: Iterable[int]) -> str:
    """Format sorted IDs with normalized names and distinct differing originals."""
    ingredients = []
    for ingredient_id in sorted(set(ingredient_ids)):
        name = (recipe.ingredient_names.get(ingredient_id) or "").strip()
        originals = sorted({
            original.strip()
            for original in recipe.ingredient_original_names.get(ingredient_id, ())
            if original.strip() and original.strip() != name
        })
        parts = [name] if name else []
        if originals:
            parts.append(f"[원본: {', '.join(originals)}]")
        parts.append(f"({ingredient_id})")
        ingredients.append(" ".join(parts))
    return "; ".join(ingredients)


def run(args: argparse.Namespace) -> None:
    """Run the local comparison and write summaries, differences, and diagnostics.

    SQLite is opened with ``mode=ro``. The only writes are report files under
    ``output_dir``. Source classification conflicts are reported separately
    from optional, explicitly reviewed semantic annotations; counterfactual
    sensitivity rows never overwrite the default rule decisions.
    """
    available_ids = frozenset(args.fridge_ids)
    excluded_match_ids = frozenset(getattr(args, "excluded_match_ids", ()))
    thresholds = tuple(args.d_thresholds)
    rules = build_rules(thresholds)
    annotations = load_semantic_annotations(args.semantic_review)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    uri = args.db.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True) as connection:
        recipes = load_recipes(connection)

    recipes_by_id = {recipe.recipe_id: recipe for recipe in recipes}
    metrics_by_id = {
        recipe.recipe_id: calculate_metrics(recipe, available_ids, excluded_match_ids)
        for recipe in recipes
    }
    decisions = {
        recipe_id: {rule.rule_id: evaluate_rule(rule, metrics) for rule in rules}
        for recipe_id, metrics in metrics_by_id.items()
    }

    summary: list[dict[str, object]] = []
    for rule in rules:
        candidates = [
            metrics_by_id[recipe_id]
            for recipe_id in metrics_by_id
            if decisions[recipe_id][rule.rule_id][0]
        ]
        summary.append({
            "rule": rule.rule_id,
            "criterion": rule.description,
            "candidate_count": len(candidates),
            "candidate_fraction": len(candidates) / len(recipes) if recipes else None,
            "mean_total_coverage": _mean(item.total_coverage for item in candidates),
            "median_total_coverage": _median(item.total_coverage for item in candidates),
            "mean_general_coverage": _mean(item.general_coverage for item in candidates),
            "median_general_coverage": _median(item.general_coverage for item in candidates),
            "mean_main_coverage": _mean(item.main_coverage for item in candidates),
            "median_main_coverage": _median(item.main_coverage for item in candidates),
        })
    _write_csv(args.output_dir / "candidate_summary.csv", summary)

    detail_rows = []
    for recipe_id, metrics in metrics_by_id.items():
        row = _metrics_row(metrics)
        for rule in rules:
            row[f"pass_{rule.rule_id}"] = decisions[recipe_id][rule.rule_id][0]
            row[f"reason_{rule.rule_id}"] = decisions[recipe_id][rule.rule_id][1]
        detail_rows.append(row)
    metric_fields = list(_metrics_row(next(iter(metrics_by_id.values())))) if metrics_by_id else [
        "recipe_id", "recipe_name", "total_ingredients", "total_matches", "total_coverage",
        "general_ingredients", "general_matches", "general_coverage", "main_ingredients",
        "main_matches", "main_coverage", "seasoning_ingredients", "seasoning_matches",
        "type_conflict_ids", "main_seasoning_conflict_ids",
    ]
    for rule in rules:
        metric_fields.extend([f"pass_{rule.rule_id}", f"reason_{rule.rule_id}"])
    _write_csv(args.output_dir / "recipe_metrics.csv", detail_rows, metric_fields)

    difference_rows: list[dict[str, object]] = []
    for left_index, left in enumerate(rules):
        for right in rules[left_index + 1:]:
            for recipe_id, metrics in metrics_by_id.items():
                left_pass, left_reason = decisions[recipe_id][left.rule_id]
                right_pass, right_reason = decisions[recipe_id][right.rule_id]
                if left_pass == right_pass:
                    continue
                (
                    present_ids,
                    absent_ids,
                    present_main_ids,
                    absent_main_ids,
                ) = _ingredient_match_details(recipes_by_id[recipe_id], available_ids)
                difference_rows.append({
                    "rule_left": left.rule_id,
                    "rule_right": right.rule_id,
                    "direction": f"{left.rule_id}_pass_{right.rule_id}_fail" if left_pass else f"{right.rule_id}_pass_{left.rule_id}_fail",
                    "recipe_id": recipe_id,
                    "recipe_name": metrics.name,
                    "left_reason": left_reason,
                    "right_reason": right_reason,
                    "matched_ingredients": _format_ingredients(recipes_by_id[recipe_id], present_ids),
                    "missing_ingredients": _format_ingredients(recipes_by_id[recipe_id], absent_ids),
                    "matched_main_ingredients": _format_ingredients(recipes_by_id[recipe_id], present_main_ids),
                    "missing_main_ingredients": _format_ingredients(recipes_by_id[recipe_id], absent_main_ids),
                    **_metrics_row(metrics),
                })
    difference_fields = [
        "rule_left", "rule_right", "direction", "recipe_id", "recipe_name",
        "left_reason", "right_reason", *metric_fields[:15],
        "matched_ingredients", "missing_ingredients",
        "matched_main_ingredients", "missing_main_ingredients",
    ]
    _write_csv(args.output_dir / "rule_differences.csv", difference_rows, difference_fields)

    conflict_rows: list[dict[str, object]] = []
    semantic_rows: list[dict[str, object]] = []
    for recipe in recipes:
        for ingredient_id, raw_types in recipe.ingredient_types.items():
            if len(raw_types) > 1:
                conflict_rows.append({
                    "recipe_id": recipe.recipe_id,
                    "recipe_name": recipe.name,
                    "ingredient_id": ingredient_id,
                    "ingredient_name": recipe.ingredient_names.get(ingredient_id, ""),
                    "source_types": ";".join(sorted(raw_types)),
                    "priority_resolution": min(raw_types, key=lambda item: {MAIN: 0, SECONDARY: 1, SEASONING: 2}[item]),
                    "includes_main_and_seasoning": MAIN in raw_types and SEASONING in raw_types,
                })
            if ingredient_id in annotations:
                semantic_type, reason = annotations[ingredient_id]
                source_type = min(raw_types, key=lambda item: {MAIN: 0, SECONDARY: 1, SEASONING: 2}[item]) if raw_types else None
                semantic_rows.append({
                    "recipe_id": recipe.recipe_id,
                    "recipe_name": recipe.name,
                    "ingredient_id": ingredient_id,
                    "ingredient_name": recipe.ingredient_names.get(ingredient_id, ""),
                    "source_types": ";".join(sorted(raw_types)),
                    "reviewed_semantic_type": semantic_type,
                    "review_reason": reason,
                    "source_conflict": len(raw_types) > 1,
                    "source_effective_type": source_type or "",
                    "explicit_semantic_mismatch": source_type is not None and source_type != semantic_type,
                })
    _write_csv(args.output_dir / "type_conflicts.csv", conflict_rows,
               ["recipe_id", "recipe_name", "ingredient_id", "ingredient_name", "source_types", "priority_resolution", "includes_main_and_seasoning"])

    types_by_ingredient: dict[int, set[str]] = defaultdict(set)
    recipes_by_ingredient: dict[int, set[int]] = defaultdict(set)
    names_by_ingredient: dict[int, str] = {}
    for recipe in recipes:
        for ingredient_id, raw_types in recipe.ingredient_types.items():
            types_by_ingredient[ingredient_id].update(raw_types)
            recipes_by_ingredient[ingredient_id].add(recipe.recipe_id)
            names_by_ingredient[ingredient_id] = recipe.ingredient_names.get(ingredient_id, "")
    variation_rows = [
        {
            "ingredient_id": ingredient_id,
            "ingredient_name": names_by_ingredient.get(ingredient_id, ""),
            "source_types_across_recipes": ";".join(sorted(types)),
            "recipe_count": len(recipes_by_ingredient[ingredient_id]),
            "variation_kind": "across_recipes; not a within-recipe duplicate conflict",
        }
        for ingredient_id, types in sorted(types_by_ingredient.items())
        if len(types) > 1
    ]
    _write_csv(args.output_dir / "type_variations_across_recipes.csv", variation_rows,
               ["ingredient_id", "ingredient_name", "source_types_across_recipes", "recipe_count", "variation_kind"])

    _write_csv(args.output_dir / "semantic_reviews.csv", semantic_rows,
               ["recipe_id", "recipe_name", "ingredient_id", "ingredient_name", "source_types", "reviewed_semantic_type", "review_reason", "source_conflict", "source_effective_type", "explicit_semantic_mismatch"])

    # Conflict sensitivity is explicitly counterfactual: when a recipe+ID has
    # both main and seasoning rows, recalculate as seasoning and report changes.
    conflict_sensitivity_rows: list[dict[str, object]] = []
    semantic_impact_rows: list[dict[str, object]] = []
    for recipe in recipes:
        main_seasoning_ids = tuple(
            ingredient_id for ingredient_id, types in recipe.ingredient_types.items()
            if MAIN in types and SEASONING in types
        )
        if main_seasoning_ids:
            changed_types = dict(recipe.ingredient_types)
            for ingredient_id in main_seasoning_ids:
                changed_types[ingredient_id] = frozenset(
                    recipe.ingredient_types[ingredient_id] - {MAIN}
                )
            alternate = Recipe(recipe.recipe_id, recipe.name, changed_types, recipe.ingredient_names)
            alternate_metrics = calculate_metrics(alternate, available_ids, excluded_match_ids)
            for rule in rules:
                before = decisions[recipe.recipe_id][rule.rule_id]
                after = evaluate_rule(rule, alternate_metrics)
                conflict_sensitivity_rows.append({
                    "recipe_id": recipe.recipe_id,
                    "recipe_name": recipe.name,
                    "ingredient_ids_reclassified_for_sensitivity_only": ";".join(map(str, main_seasoning_ids)),
                    "rule": rule.rule_id,
                    "default_pass": before[0],
                    "counterfactual_pass": after[0],
                    "decision_changed": before[0] != after[0],
                    "default_reason": before[1],
                    "counterfactual_reason": after[1],
                    "default_main_matches": metrics_by_id[recipe.recipe_id].main_matches,
                    "counterfactual_main_matches": alternate_metrics.main_matches,
                    "default_general_matches": metrics_by_id[recipe.recipe_id].general_matches,
                    "counterfactual_general_matches": alternate_metrics.general_matches,
                })

        reviewed_ids = [ingredient_id for ingredient_id in recipe.ingredient_types if ingredient_id in annotations]
        if reviewed_ids:
            changed_types = dict(recipe.ingredient_types)
            for ingredient_id in reviewed_ids:
                changed_types[ingredient_id] = frozenset({annotations[ingredient_id][0]})
            reviewed = Recipe(recipe.recipe_id, recipe.name, changed_types, recipe.ingredient_names)
            reviewed_metrics = calculate_metrics(reviewed, available_ids, excluded_match_ids)
            for rule in rules:
                before = decisions[recipe.recipe_id][rule.rule_id]
                after = evaluate_rule(rule, reviewed_metrics)
                semantic_impact_rows.append({
                    "recipe_id": recipe.recipe_id,
                    "recipe_name": recipe.name,
                    "reviewed_ingredient_ids_applied_together": ";".join(map(str, reviewed_ids)),
                    "rule": rule.rule_id,
                    "default_pass": before[0],
                    "reviewed_pass": after[0],
                    "decision_changed": before[0] != after[0],
                    "default_reason": before[1],
                    "reviewed_reason": after[1],
                })
    _write_csv(args.output_dir / "type_conflict_sensitivity.csv", conflict_sensitivity_rows,
               ["recipe_id", "recipe_name", "ingredient_ids_reclassified_for_sensitivity_only", "rule", "default_pass", "counterfactual_pass", "decision_changed", "default_reason", "counterfactual_reason", "default_main_matches", "counterfactual_main_matches", "default_general_matches", "counterfactual_general_matches"])
    _write_csv(args.output_dir / "semantic_review_impact.csv", semantic_impact_rows,
               ["recipe_id", "recipe_name", "reviewed_ingredient_ids_applied_together", "rule", "default_pass", "reviewed_pass", "decision_changed", "default_reason", "reviewed_reason"])

    metadata = {
        "database": str(args.db.resolve()),
        "available_ingredient_ids": sorted(available_ids),
        "d_thresholds": list(thresholds),
        "recipe_count": len(recipes),
        "semantic_annotation_count": len(annotations),
        "type_assignment_policy": "per recipe+ingredient, main > secondary > seasoning; unknown types count only in total metrics",
        "semantic_policy": "no semantic reclassification is inferred; semantic_reviews.csv contains only explicit annotations",
        "type_conflict_policy": "type_conflicts.csv identifies within-recipe same-ID conflicts; type_variations_across_recipes.csv separately shows cross-recipe variation; sensitivity output is counterfactual only",
        "b_and_e_note": "B (general_matches >= 1) equals an OR rule adding general_coverage > 0 when denominator is nonzero; no separate E rule is run",
    }
    if excluded_match_ids:
        metadata["excluded_match_ids"] = sorted(excluded_match_ids)
        metadata["match_exclusion_policy"] = (
            "exclude IDs from all match numerators only; preserve denominators "
            "and inventory availability, including matched/missing ingredient display"
        )
    (args.output_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote experiment outputs to {args.output_dir.resolve()}")


def _positive_id(value: str) -> int:
    """Parse a positive normalized ingredient ID for the command line."""
    try:
        result = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("IDs must be integers") from exc
    if result <= 0:
        raise argparse.ArgumentTypeError("IDs must be positive")
    return result


def _threshold(value: str) -> float:
    """Parse a D-rule coverage threshold in the interval ``(0, 1]``."""
    try:
        result = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("thresholds must be numbers") from exc
    if not 0 < result <= 1:
        raise argparse.ArgumentTypeError("thresholds must be greater than 0 and at most 1")
    return result


def main() -> None:
    """Parse local experiment options and invoke the SQLite-backed runner."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=REPO_ROOT / "data/recipes/recipes.sqlite3")
    parser.add_argument("--fridge-ids", type=_positive_id, nargs="+", required=True)
    parser.add_argument("--excluded-match-ids", type=_positive_id, nargs="+", default=(),
                        help="experimental IDs excluded from match numerators only")
    parser.add_argument("--d-thresholds", type=_threshold, nargs="+", default=(0.25, 0.5, 0.75))
    parser.add_argument("--output-dir", type=Path, default=REPO_ROOT / "data/recipes/filtering-experiments")
    parser.add_argument("--semantic-review", type=Path,
                        help="optional human-reviewed CSV: ingredient_id,semantic_type,reason")
    args = parser.parse_args()
    if not args.db.is_file():
        parser.error(f"SQLite database does not exist: {args.db}")
    run(args)


if __name__ == "__main__":
    main()
