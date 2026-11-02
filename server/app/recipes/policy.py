"""Initial service policy; replace through injection when comparing policies.

Counts use distinct IDs and main > secondary > seasoning for conflicting rows.
Water and the assumed seasonings (``SeasoningPolicy``) are removed from matched and missing totals;
unknown types count in totals only. This projection never changes AI inputs.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

from app.recipes.seasonings import load_seasoning_policy
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
from recipe_revision.seasoning import SeasoningPolicy

WORKERS_ENV = "RECIPE_REVISION_WORKERS"
PRESCREEN_ENV = "RECIPE_REVISION_PRESCREEN"
RETRY_ENV = "RECIPE_REVISION_RETRY"
TYPE_CODES = {"3060001": MAIN, "3060002": SECONDARY, "3060003": SEASONING}


@dataclass(frozen=True)
class RecommendationPolicy:
    """Server-owned selection parameters; default C is an initial service choice."""

    rule_id: str = "C"
    general_minimum: int = 2
    main_minimum: int = 1
    # Types dropped from the counts entirely. Seasonings are governed by ``seasonings`` below, not
    # by this set, so the filter and the revision request use the same assumption.
    excluded_types: frozenset[str] = frozenset()
    water_id: int = 204
    default_revision_limit: int = 3
    maximum_revision_limit: int = 5
    # Which seasonings are assumed to be at home (the declared list in assumed_seasonings.json by
    # default).
    # Assumed ingredients are left out of the matched/missing counts and are marked available in the
    # revision request and post-check; every other ingredient must be in the inventory.
    seasonings: SeasoningPolicy = field(default_factory=load_seasoning_policy)
    # Concurrent revision calls per request. 1 keeps the sequential loop (later candidates are not
    # called after a shared failure); more calls all selected candidates at once and returns the
    # same response as the sequential loop would for the same per-call outcomes.
    revision_workers: int = 1
    # Candidates whose dish-name ingredient is unavailable are refused without a model call.
    # "off"; "refuse" (the candidate keeps its slot); "fill" (the next candidates take over, so the
    # model is called for ``limit`` candidates when enough exist).
    prescreen: str = "refuse"
    # Ask the model once more, with feedback, after a rejected answer (one extra call).
    retry_on_rejection: bool = False
    # Add an omission entry to the change list for each removed ingredient it does not mention.
    complete_changes: bool = True

    @classmethod
    def from_env(cls, env: Mapping[str, str], **overrides) -> "RecommendationPolicy":
        """Read the revision options that may change without a code edit; unset keeps the default.

        ``RECIPE_REVISION_WORKERS`` (1-5, concurrent model calls per request),
        ``RECIPE_REVISION_PRESCREEN`` (off, refuse or fill) and ``RECIPE_REVISION_RETRY``
        (true or false, one extra call after a rejected answer).
        """
        options = dict(overrides)
        if env.get(WORKERS_ENV):
            try:
                options["revision_workers"] = int(env[WORKERS_ENV])
            except ValueError as exc:
                raise ValueError(
                    f"{WORKERS_ENV} must be an integer, got {env[WORKERS_ENV]!r}"
                ) from exc
        if env.get(PRESCREEN_ENV):
            options["prescreen"] = env[PRESCREEN_ENV].strip().lower()
        if env.get(RETRY_ENV):
            value = env[RETRY_ENV].strip().lower()
            if value not in ("true", "false", "1", "0"):
                raise ValueError(f"{RETRY_ENV} must be true or false, got {env[RETRY_ENV]!r}")
            options["retry_on_rejection"] = value in ("true", "1")
        return cls(**options)

    def __post_init__(self):
        if self.general_minimum < 1 or self.main_minimum < 1:
            raise ValueError("Match thresholds must be positive")
        if not 1 <= self.default_revision_limit <= self.maximum_revision_limit <= 5:
            raise ValueError("Revision limits must be within 1 through 5")
        if not 1 <= self.revision_workers <= self.maximum_revision_limit:
            raise ValueError("Revision workers must be between 1 and the maximum revision limit")
        if self.prescreen not in ("off", "refuse", "fill"):
            raise ValueError("prescreen must be off, refuse or fill")
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
            if (
                ingredient_id != self.water_id
                and resolved not in self.excluded_types
                and not self.seasonings.assumed(ingredient_id, resolved == SEASONING)
            ):
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
