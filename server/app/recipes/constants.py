# AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
"""Ingredient naming rules shared by recognition and recommendation."""

# Seasonings a one-person household is assumed to always have. Chosen from the most
# frequent seasoning rows in RecipeIngredient.csv (team decision D1, 2026-10-11).
STAPLE_SEASONINGS: tuple[str, ...] = (
    "물",
    "소금",
    "설탕",
    "간장",
    "후춧가루",
    "식용유",
    "참기름",
    "깨소금",
    "다진마늘",
    "고춧가루",
)

# The recipe source stores some synonyms as separate ingredients (e.g. 계란 and 달걀).
# Only exact equivalents; substitutions such as 국간장 for 진간장 are a pending team decision.
_SYNONYM_GROUPS: tuple[frozenset[str], ...] = (
    frozenset({"계란", "달걀"}),
    frozenset({"참치", "참치캔", "참치통조림"}),
    frozenset({"김치", "배추김치"}),
    frozenset({"후추", "후춧가루"}),
)

# Owning the left ingredient means the right forms can be prepared from it at home.
_PREPARED_FORMS: dict[str, tuple[str, ...]] = {
    "대파": ("다진파",),
}


def with_synonyms(names: list[str] | tuple[str, ...]) -> set[str]:
    expanded = {name.strip() for name in names if name.strip()}
    for name in list(expanded):
        expanded.update(_PREPARED_FORMS.get(name, ()))
    for group in _SYNONYM_GROUPS:
        if expanded & group:
            expanded |= group
    return expanded
