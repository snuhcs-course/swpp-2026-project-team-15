# AI-generated with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
"""Exact synonyms between ingredient names (kept small on purpose)."""

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


def with_synonyms(names: list[str] | tuple[str, ...]) -> set[str]:
    expanded = {name.strip() for name in names if name.strip()}
    for name in list(expanded):
        expanded.update(PREPARED_FORMS.get(name, ()))
    for group in SYNONYM_GROUPS:
        if expanded & group:
            expanded |= group
    return expanded
