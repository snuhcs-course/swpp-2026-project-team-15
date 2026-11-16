# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""The baseline dish list and the deterministic matching on top of it."""

import json
import os
from dataclasses import dataclass
from pathlib import Path

from app.recipes.constants import with_synonyms
from app.recipes.seasonings import DEFAULT_FILE as SEASONING_FILE
from app.recipes.seasonings import FILE_ENV as SEASONING_FILE_ENV

DEFAULT_DATA = Path(__file__).with_name("dishes.json")
DATA_ENV = "DISH_DATA_FILE"
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
    """Names assumed at home: the same list the recipe policy uses, plus water."""
    file = Path(path or os.environ.get(SEASONING_FILE_ENV) or SEASONING_FILE)
    try:
        assumed = json.loads(file.read_text(encoding="utf-8")).get("assumed", [])
        names = {str(item["name"]) for item in assumed}
    except (OSError, ValueError, KeyError, TypeError):
        names = set()
    return frozenset(names | {WATER})


class Catalog:
    def __init__(self, data: dict, staples: frozenset[str]):
        self.staples = staples
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

    @classmethod
    def load(cls, path: Path | str | None = None, staples: frozenset[str] | None = None):
        file = Path(path or os.environ.get(DATA_ENV) or DEFAULT_DATA)
        data = json.loads(file.read_text(encoding="utf-8"))
        return cls(data, load_staples() if staples is None else staples)

    def __len__(self) -> int:
        return len(self.dishes)

    def get(self, dish_id: str) -> Dish | None:
        return self.dishes.get(dish_id)

    def owned(self, ingredients: list[str]) -> set[str]:
        """Names the user has, widened by synonyms and by what an item can stand in for."""
        names = {n.strip().replace(" ", "") for n in ingredients if n and n.strip()}
        owned = with_synonyms(sorted(names))
        for key, alts in self.equivalents.items():
            if key in owned or owned & set(alts):
                owned.add(key)
                owned.update(alts)
        return owned

    def match(self, dish: Dish, owned: set[str]) -> Match:
        have, missing = [], []
        for key in dish.key_ingredients:
            if key in self.staples or set(self.equivalents.get(key, ())) & self.staples:
                continue  # assumed at home (e.g. 마늘 is covered by the staple 다진마늘)
            (have if self._covered(key, owned) else missing).append(key)
        return Match(dish, tuple(have), tuple(missing))

    def _covered(self, key: str, owned: set[str]) -> bool:
        return key in owned or bool(with_synonyms([key]) & owned)

    def rank(self, ingredients: list[str]) -> list[Match]:
        """Dishes with at least one owned main ingredient, fewest missing first."""
        owned = self.owned(ingredients)
        matches = [m for d in self.dishes.values() if (m := self.match(d, owned)).have]
        matches.sort(key=lambda m: (len(m.missing), -len(m.have), m.dish.id))
        return matches

    def usable(self, name: str, owned: set[str]) -> bool:
        return name in self.staples or self._covered(name, owned)
