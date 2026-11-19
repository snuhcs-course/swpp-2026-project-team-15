# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Exact synonyms between ingredient names (kept small on purpose), and the one spelling rule.

Every module that compares ingredient names uses ``compact`` and ``with_synonyms`` from here; a
second copy had already drifted (server review, 2026-11-19).
"""

from collections.abc import Iterable

# Only exact equivalents; substitutions belong to the table in dishes.json.
SYNONYM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"계란", "달걀"}),
    frozenset({"참치", "참치캔", "참치통조림"}),
    frozenset({"김치", "배추김치"}),
    frozenset({"후추", "후춧가루"}),
)

# Owning the left ingredient means the right forms can be prepared from it at home.
PREPARED_FORMS: dict[str, tuple[str, ...]] = {
    "대파": ("다진파",),
}


def compact(name: str) -> str:
    """A name without surrounding or inner spaces: the one spelling rule of every lookup."""
    return name.strip().replace(" ", "")


def with_synonyms(names: Iterable[str], *, prepared: bool = True) -> set[str]:
    """The names plus every spelling of their synonym groups and, with ``prepared``, the forms
    made from them at home (대파 -> 다진파). The cards' choices and the recipe name table use
    ``prepared=False``: owning 대파 does not make a recipe's 다진파 a separate owned row there."""
    expanded = {name.strip() for name in names if name.strip()}
    if prepared:
        for name in list(expanded):
            expanded.update(PREPARED_FORMS.get(name, ()))
    for group in SYNONYM_GROUPS:
        if expanded & group:
            expanded |= group
    return expanded
