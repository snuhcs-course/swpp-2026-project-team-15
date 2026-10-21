"""Initial service policy; replace through injection when comparing policies.

Counts use distinct IDs and main > secondary > seasoning for conflicting rows.
Water and resolved seasonings are removed from both matched and missing totals;
unknown types count in totals only. This projection never changes AI inputs.
"""

from dataclasses import dataclass

from recipe_filtering.metrics import (
    MAIN,
    SEASONING,
    SECONDARY,
    TYPE_PRIORITY,
    RecipeMetrics,
    calculate_metrics,
)
from recipe_filtering.metrics import Recipe as FilteringRecipe
from recipe_filtering.rules import build_rules, evaluate_rule
from recipe_revision.models import SourceRecipe

TYPE_CODES = {"3060001": MAIN, "3060002": SECONDARY, "3060003": SEASONING}


@dataclass(frozen=True)
class RecommendationPolicy:
    """Server-owned selection parameters; default C is an initial service choice."""

    rule_id: str = "C"
    general_minimum: int = 2
    main_minimum: int = 1
    excluded_types: frozenset[str] = frozenset({SEASONING})
    water_id: int = 204
    default_revision_limit: int = 3
    maximum_revision_limit: int = 5

    def __post_init__(self):
        if self.general_minimum < 1 or self.main_minimum < 1:
            raise ValueError("Match thresholds must be positive")
        if not 1 <= self.default_revision_limit <= self.maximum_revision_limit <= 5:
            raise ValueError("Revision limits must be within 1 through 5")
        if self.water_id <= 0:
            raise ValueError("Water ID must be positive")
        if self.rule_id not in {rule.rule_id for rule in build_rules()}:
            raise ValueError("Unsupported filtering rule")

    def metrics(self, source: SourceRecipe, available: frozenset[int]) -> RecipeMetrics:
        """Project source classifications into counts without modifying source rows."""
        types: dict[int, set[str]] = {}
        names = {}
        for row in source.ingredients:
            types.setdefault(row.ingredient_id, set()).add(
                TYPE_CODES.get(row.ingredient_type_code, row.ingredient_type or "")
            )
            names[row.ingredient_id] = row.name
        included = {}
        for ingredient_id, labels in types.items():
            known = labels & TYPE_PRIORITY.keys()
            resolved = min(known, key=TYPE_PRIORITY.__getitem__) if known else None
            if ingredient_id != self.water_id and resolved not in self.excluded_types:
                included[ingredient_id] = frozenset(labels)
        return calculate_metrics(
            FilteringRecipe(source.recipe_id, source.name, included, names), available
        )

    def accepts(self, metrics: RecipeMetrics) -> bool:
        """Evaluate a supported reusable rule with server-owned C thresholds."""
        rule = next(rule for rule in build_rules() if rule.rule_id == self.rule_id)
        return evaluate_rule(
            rule, metrics, general_minimum=self.general_minimum, main_minimum=self.main_minimum
        )[0]


DEFAULT_POLICY = RecommendationPolicy()
