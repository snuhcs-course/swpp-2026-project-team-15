"""Pure data structures and deterministic ingredient matching metrics."""
# AI-generated initial implementation with Codex (GPT-6 Luna Medium),
# 2026-10-13 to 2026-10-17; reviewed and revised by Soohyun An.

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

MAIN = "주재료"
SECONDARY = "부재료"
SEASONING = "양념"
TYPE_PRIORITY = {MAIN: 0, SECONDARY: 1, SEASONING: 2}
# This resolves conflicts reproducibly as in the existing experiment log; it
# does not claim that the source's main/secondary/seasoning labels are correct.


@dataclass(frozen=True)
class Recipe:
    """Framework-independent recipe input for deterministic filtering.

    ``ingredient_types`` is keyed by normalized ingredient ID and retains all
    distinct source types seen for that ID in this recipe. An empty type set
    represents a missing or unrecognized classification. ``ingredient_names``
    is diagnostic display data only; matching never uses names.
    """

    recipe_id: int
    name: str
    # Keep every distinct source type for each normalized ID. This preserves
    # within-recipe type conflicts for diagnostics instead of hiding them.
    ingredient_types: Mapping[int, frozenset[str]]
    ingredient_names: Mapping[int, str]

    # Preserve original ingredient names for review and AI revision
    ingredient_original_names: Mapping[int, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class RecipeMetrics:
    """Counts and coverage rates for one recipe against an inventory.

    ``total_*`` uses every distinct recipe ingredient ID. ``general_*`` uses
    resolved main and secondary ingredients, while ``main_*`` and
    ``seasoning_*`` use their corresponding resolved types. Each coverage
    denominator is the ingredient count for that metric; rates are ``None``
    when a denominator is zero. Conflict ID fields preserve source
    classification issues for later explanation and sensitivity analysis;
    they do not imply a semantic misclassification.
    """

    recipe_id: int
    name: str
    total_ingredients: int
    total_matches: int
    total_coverage: float | None
    general_ingredients: int
    general_matches: int
    general_coverage: float | None
    main_ingredients: int
    main_matches: int
    main_coverage: float | None
    seasoning_ingredients: int
    seasoning_matches: int
    conflicting_ingredient_ids: tuple[int, ...]
    main_seasoning_conflict_ids: tuple[int, ...]


def _resolved_type(types: frozenset[str]) -> str | None:
    """Resolve recognized source types using the experiment's fixed priority.

    The priority makes counts reproducible when a recipe/ingredient pair has
    conflicting rows. Unrecognized or missing types do not contribute to
    type-specific counts.
    """
    known = [value for value in types if value in TYPE_PRIORITY]
    return min(known, key=TYPE_PRIORITY.__getitem__) if known else None


def _ratio(numerator: int, denominator: int) -> float | None:
    """Return a coverage rate, preserving an undefined zero-denominator case."""
    return numerator / denominator if denominator else None


def calculate_metrics(
    recipe: Recipe,
    available_ids: frozenset[int],
    excluded_match_ids: frozenset[int] = frozenset(),
) -> RecipeMetrics:
    """Calculate exact normalized-ID counts and rates for one recipe.

    Total metrics include every distinct recipe ingredient ID, including IDs
    without a recognized type. General means resolved main plus secondary;
    main and seasoning metrics use the resolved type. Duplicate source rows
    count once per ID. Matching is exact and does not infer equivalence,
    omission, substitution, or recipe feasibility.

    Args:
        recipe: Recipe data with source types retained for conflict reporting.
        available_ids: User inventory as normalized ingredient IDs.
        excluded_match_ids: Experimental IDs omitted from match numerators
            only. Ingredient counts and coverage denominators stay unchanged;
            these IDs remain available in the inventory.

    Returns:
        Counts, coverage rates, and the source-conflict IDs for this recipe.
    """
    total = general = main = seasoning = 0
    total_matches = general_matches = main_matches = seasoning_matches = 0
    conflicts: list[int] = []
    main_seasoning_conflicts: list[int] = []

    for ingredient_id, raw_types in recipe.ingredient_types.items():
        resolved = _resolved_type(raw_types)
        matched = ingredient_id in available_ids and ingredient_id not in excluded_match_ids
        total += 1
        total_matches += int(matched)
        if len(raw_types) > 1:
            conflicts.append(ingredient_id)
        if MAIN in raw_types and SEASONING in raw_types:
            main_seasoning_conflicts.append(ingredient_id)

        # Unknown and NULL classifications contribute only to total coverage.
        if resolved in (MAIN, SECONDARY):
            general += 1
            general_matches += int(matched)
        if resolved == MAIN:
            main += 1
            main_matches += int(matched)
        elif resolved == SEASONING:
            seasoning += 1
            seasoning_matches += int(matched)

    return RecipeMetrics(
        recipe_id=recipe.recipe_id,
        name=recipe.name,
        total_ingredients=total,
        total_matches=total_matches,
        total_coverage=_ratio(total_matches, total),
        general_ingredients=general,
        general_matches=general_matches,
        general_coverage=_ratio(general_matches, general),
        main_ingredients=main,
        main_matches=main_matches,
        main_coverage=_ratio(main_matches, main),
        seasoning_ingredients=seasoning,
        seasoning_matches=seasoning_matches,
        conflicting_ingredient_ids=tuple(sorted(conflicts)),
        main_seasoning_conflict_ids=tuple(sorted(main_seasoning_conflicts)),
    )
