# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""The baseline dish list and the deterministic matching on top of it."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from app.dishes.synonyms import compact, with_synonyms

if TYPE_CHECKING:
    from app.dishes.roles import Availability

DEFAULT_DATA = Path(__file__).with_name("dishes.json")
STAPLES_FILE = Path(__file__).with_name("staples.json")
WATER = "물"


@dataclass(frozen=True)
class Dish:
    id: str
    name: str
    category: str
    key_ingredients: tuple[str, ...]
    optional: frozenset[str]
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class Match:
    dish: Dish
    have: tuple[str, ...]
    missing: tuple[str, ...]


def load_staples(path: Path | str | None = None) -> frozenset[str]:
    """Names assumed at home: the staples list plus water."""
    file = Path(path or STAPLES_FILE)
    try:
        names = {str(name) for name in json.loads(file.read_text(encoding="utf-8"))["staples"]}
    except (OSError, ValueError, KeyError, TypeError):
        names = set()
    return frozenset(names | {WATER})


class Catalog:
    """The dish list. With ``names`` (the reviewed name table, recipe_names.py) ownership is
    decided by that one rule, the same as on the cards and in the recipe view; without it, by the
    list's own ``equivalents`` (kept for the research replays)."""

    def __init__(self, data: dict, staples: frozenset[str], names: "Availability | None" = None):
        self.staples = staples
        self._names = names
        self.equivalents = {k: tuple(v) for k, v in data.get("equivalents", {}).items()}
        self.substitutes = {k: tuple(v) for k, v in data.get("substitutes", {}).items()}
        self.dishes: dict[str, Dish] = {}
        for raw in data["dishes"]:
            dish = Dish(
                id=raw["id"],
                name=raw["name"],
                category=raw["category"],
                key_ingredients=tuple(raw["key_ingredients"]),
                optional=frozenset(raw.get("optional", [])),
                aliases=tuple(raw.get("aliases", [])),
            )
            if dish.id in self.dishes:
                raise ValueError(f"duplicate dish id {dish.id}")
            self.dishes[dish.id] = dish
        self._by_name = {d.name: d for d in self.dishes.values()}

    @classmethod
    def load(
        cls,
        path: Path | str | None = None,
        staples: frozenset[str] | None = None,
        names: "Availability | None" = None,
    ):
        file = Path(path or DEFAULT_DATA)
        data = json.loads(file.read_text(encoding="utf-8"))
        return cls(data, load_staples() if staples is None else staples, names)

    def __len__(self) -> int:
        return len(self.dishes)

    def get(self, dish_id: str) -> Dish | None:
        return self.dishes.get(dish_id)

    def by_name(self, name: str) -> Dish | None:
        return self._by_name.get(name)

    def all(self) -> list[Dish]:
        return list(self.dishes.values())

    def owned(self, ingredients: list[str]) -> set[str]:
        """Names the user has, widened by synonyms and by what an item can stand in for."""
        if self._names is not None:
            return self._names.owned(ingredients)
        names = {compact(n) for n in ingredients if n and n.strip()}
        owned = with_synonyms(sorted(names))
        for key, alts in self.equivalents.items():
            if key in owned or owned & set(alts):
                owned.add(key)
                owned.update(alts)
        return owned

    def uses(self, dish: Dish, item: str) -> bool:
        """Whether the user's ``item`` is one of the dish's ingredients (key or optional), by the
        same ownership rule as everywhere else. A staple assumed at home does not count: owning
        초콜릿 must not make a dish that needs only 소금 look like it uses 초콜릿."""
        owned = self.owned([item])
        for key in set(dish.key_ingredients) | set(dish.optional):
            if self._names is not None:
                if self._names.status(key, owned) == "owned":
                    return True
            elif self.status(key, owned) == "owned":
                return True
        return False

    def match(self, dish: Dish, owned: set[str]) -> Match:
        have, missing = [], []
        for key in dish.key_ingredients:
            if key in self.staples or set(self.equivalents.get(key, ())) & self.staples:
                continue  # assumed at home (e.g. 마늘 is covered by the staple 다진마늘)
            (have if self._covered(key, owned) else missing).append(key)
        return Match(dish, tuple(have), tuple(missing))

    def _covered(self, key: str, owned: set[str]) -> bool:
        if self._names is not None:
            return self._names.status(key, owned) != "unavailable"
        return key in owned or bool(with_synonyms([key]) & owned)

    def status(self, name: str, owned: set[str]) -> str:
        """'assumed' for a staple at home, 'owned' when the user has it, else 'unavailable'."""
        key = compact(name)
        if key in self.staples or set(self.equivalents.get(key, ())) & self.staples:
            return "assumed"
        return "owned" if self._covered(key, owned) else "unavailable"

    def rank(self, ingredients: list[str]) -> list[Match]:
        """Every dish sharing a main ingredient with the owned ones: fewest missing, then name."""
        owned = self.owned(ingredients)
        matches = [m for d in self.dishes.values() if (m := self.match(d, owned)).have]
        matches.sort(key=lambda m: (len(m.missing), m.dish.name))
        return matches

    # -- names for autocomplete and addition suggestions without the recipe database -------------
    def ingredient_names(self) -> list[str]:
        names: set[str] = set(self.staples) - {WATER} | set(PANTRY_NAMES)
        for dish in self.dishes.values():
            names.update(dish.key_ingredients)
            names.update(dish.optional)
        for key, alts in self.equivalents.items():
            names.add(key)
            names.update(alts)
        for key, alts in self.substitutes.items():
            names.add(key)
            names.update(alts)
        return sorted(n for n in names if _plain(n))

    def additions(self, ingredients: list[str], limit: int = 5) -> list[dict]:
        """One-ingredient additions ranked by how many dishes they would complete."""
        owned = self.owned(ingredients)
        if not owned:
            return []
        ready: dict[str, list[str]] = {}
        for dish in self.dishes.values():
            match = self.match(dish, owned)
            if match.have and len(match.missing) == 1:
                ready.setdefault(match.missing[0], []).append(dish.name)
        used: dict[str, int] = {}
        for dish in self.dishes.values():
            for key in dish.key_ingredients:
                used[key] = used.get(key, 0) + 1
        ranked = sorted(ready, key=lambda n: (-len(ready[n]), -used.get(n, 0), n))
        return [
            {
                "name": n,
                "ready_recipe_count": len(ready[n]),
                "recipe_count": used.get(n, len(ready[n])),
                "ready_recipe_names": sorted(ready[n])[:5],
            }
            for n in ranked[:limit]
        ]


PANTRY_NAMES = (
    "양파",
    "대파",
    "당근",
    "계란",
    "밥",
    "두부",
    "감자",
    "김치",
    "우유",
    "식빵",
    "라면",
)


def _plain(name: str) -> bool:
    """Autocomplete names are short plain words: no digits, symbols or spaces."""
    return 0 < len(name) <= 12 and name.isalnum() and not any(c.isdigit() for c in name)
