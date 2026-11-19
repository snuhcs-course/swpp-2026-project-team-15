# AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Whether the user has each row of a stored recipe: owned, assumed (a staple) or unavailable.

Recipe rows are written from the videos (꽃소금, 진간장, 삶은 달걀) while users type plain names
(소금, 간장, 달걀). A reviewed table (recipe_names.json) says which names are the same ingredient
and which general names (고추, 버섯) are covered by owning one kind. Unlike the dish list's
stand-ins used for the cards, a stand-in is not ownership here: with 대파 the recipe's 쪽파 stays
unavailable, so the revision can replace it and say so (dish_revision study, round 3).
"""

import json
import re
from collections.abc import Iterable
from pathlib import Path

from app.dishes.catalog import load_staples
from app.dishes.synonyms import SYNONYM_GROUPS

NAMES_FILE = Path(__file__).with_name("recipe_names.json")
_PAREN = re.compile(r"\([^)]*\)")


def _plain(name: str) -> str:
    return _PAREN.sub("", name).replace(" ", "").strip()


def _synonyms(names: Iterable[str]) -> set[str]:
    forms = set(names)
    for group in SYNONYM_GROUPS:
        if forms & group:
            forms |= group
    return forms


class RecipeNames:
    def __init__(self, staples: frozenset[str], same: dict[str, str], kinds: dict[str, list[str]]):
        self._same = same
        self._kinds = {k: {self.canonical(v) for v in vs} for k, vs in kinds.items()}
        self._staples = _synonyms(self.canonical(s) for s in staples)

    @classmethod
    def load(cls, path: Path | str | None = None, staples: frozenset[str] | None = None):
        data = json.loads(Path(path or NAMES_FILE).read_text(encoding="utf-8"))
        return cls(load_staples() if staples is None else staples, data["same"], data["kinds"])

    def canonical(self, name: str) -> str:
        key = _plain(name)
        return self._same.get(key, key)

    def owned(self, ingredients: list[str]) -> set[str]:
        """The user's names in canonical form, with their exact synonyms."""
        return _synonyms(self.canonical(n) for n in ingredients if n and n.strip())

    def status(self, name: str, owned: set[str]) -> str:
        """'assumed' for a staple at home, 'owned' when the user has it, else 'unavailable'."""
        forms = _synonyms([self.canonical(name)])
        if forms & self._staples:
            return "assumed"
        if forms & owned or any(self._kinds.get(f, set()) & owned for f in forms):
            return "owned"
        return "unavailable"
