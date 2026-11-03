# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
"""Which seasonings are assumed to be at home: one object shared by candidate selection, the
revision request and the post-check, so the three cannot disagree.

``mode``:
- ``"list"``: only the declared ingredient ids are assumed available (whatever label a recipe gives
  them). Every other seasoning must be in the inventory like any other ingredient.
- ``"all"``: every ingredient a recipe labels as seasoning is assumed available.
- ``"none"``: nothing is assumed (water is handled separately by the callers).

The list is data, not logic: edit the ids in the config file, not this module. This module never
imports the app layer; the app loads the config (``app.recipes.seasonings``) and passes the object.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field

MODES = ("list", "all", "none")


class SeasoningConfigError(ValueError):
    """The seasoning configuration is unusable; the message says what to fix."""


@dataclass(frozen=True)
class SeasoningPolicy:
    mode: str = "list"
    assumed_ids: frozenset[int] = frozenset()
    # Readable names for the ids, used for validation messages and logs only.
    names: Mapping[int, str] = field(default_factory=dict, compare=False)

    def __post_init__(self):
        if self.mode not in MODES:
            raise SeasoningConfigError(f"seasoning mode must be one of {MODES}, got {self.mode!r}")
        object.__setattr__(self, "assumed_ids", frozenset(self.assumed_ids))
        bad = [
            i for i in self.assumed_ids if not isinstance(i, int) or isinstance(i, bool) or i <= 0
        ]
        if bad:
            raise SeasoningConfigError(f"assumed seasoning ids must be positive integers: {bad}")

    def assumed(self, ingredient_id: int, is_seasoning: bool) -> bool:
        """True when the ingredient counts as available without being in the inventory."""
        if self.mode == "all":
            return is_seasoning
        if self.mode == "list":
            return ingredient_id in self.assumed_ids
        return False

    def describe(self) -> str:
        if self.mode != "list":
            return self.mode
        return "list: " + ", ".join(
            f"{self.names.get(i, '?')}({i})" for i in sorted(self.assumed_ids)
        )

    @classmethod
    def from_config(cls, config: object, *, mode: str | None = None) -> "SeasoningPolicy":
        """Build from parsed JSON, shaped like ``{"mode": "list", "assumed": [{"id": 284}]}``."""
        if not isinstance(config, dict):
            raise SeasoningConfigError("seasoning config must be a JSON object")
        unknown = set(config) - {"mode", "assumed", "note"}
        if unknown:
            raise SeasoningConfigError(f"unknown seasoning config keys: {sorted(unknown)}")
        entries = config.get("assumed", [])
        if not isinstance(entries, list):
            raise SeasoningConfigError("'assumed' must be a list of {id, name} objects")
        ids: list[int] = []
        names: dict[int, str] = {}
        for entry in entries:
            if not isinstance(entry, dict) or "id" not in entry:
                raise SeasoningConfigError(f"each assumed seasoning needs an 'id': {entry!r}")
            ingredient_id = entry["id"]
            if not isinstance(ingredient_id, int) or isinstance(ingredient_id, bool):
                raise SeasoningConfigError(f"seasoning id must be an integer: {ingredient_id!r}")
            ids.append(ingredient_id)
            names[ingredient_id] = str(entry.get("name", ""))
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            raise SeasoningConfigError(f"duplicate assumed seasoning ids: {duplicates}")
        return cls(mode or config.get("mode", "list"), frozenset(ids), names)

    def check_catalog(self, catalog: Mapping[int, str]) -> None:
        """Fail early when an id is not an ingredient or its readable name disagrees.

        The ids are only used in ``list`` mode, so other modes are not checked.
        """
        if self.mode != "list":
            return
        problems = []
        for ingredient_id in sorted(self.assumed_ids):
            if ingredient_id not in catalog:
                label = self.names.get(ingredient_id, "?")
                problems.append(f"id {ingredient_id} ({label}) is not in the ingredient table")
            elif (
                self.names.get(ingredient_id)
                and self.names[ingredient_id] != catalog[ingredient_id]
            ):
                found, wanted = catalog[ingredient_id], self.names[ingredient_id]
                problems.append(
                    f"id {ingredient_id} is named {found!r} in the ingredient table, not {wanted!r}"
                )
        if problems:
            raise SeasoningConfigError(
                "seasoning config does not match the ingredient table: " + "; ".join(problems)
            )


# Behaviour of the first series (every seasoning-labelled ingredient assumed available); used as the
# default of the low-level builders so their results stay byte-identical to the evaluated requests.
ASSUME_ALL = SeasoningPolicy(mode="all")
ASSUME_NONE = SeasoningPolicy(mode="none")
