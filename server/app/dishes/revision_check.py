# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""The rules a revised recipe must obey, checked without a model call.

A result that uses an unavailable ingredient, mentions a dropped one in a step or tip, points at
a row or step that does not exist, or changes the recipe without a reason raises ``Violation``;
the caller reports it as a failure and never repairs it silently.
"""

# ruff: noqa: E501

from app.dishes.answers import strings
from app.dishes.roles import IngredientIndex
from app.dishes.schemas import Change, RecipeStep, RevisedIngredient, RevisedRecipe, SourceRecipe
from app.dishes.synonyms import with_synonyms


class Violation(Exception):
    """The model's answer breaks a rule of the check (code is machine readable)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _key(text: str) -> str:
    return text.strip().replace(" ", "")


def _kept(name: str, revised_keys: set[str]) -> bool:
    return bool(with_synonyms([_key(name)]) & revised_keys)


def check(
    data: dict,
    recipe: SourceRecipe,
    status: list[str],
    index: IngredientIndex,
    owned_names: list[str],
) -> tuple[RevisedRecipe, list[Change]]:
    """Return the revised recipe and its changes, or raise Violation. No model call."""
    owned = index.owned(owned_names)
    rows = data.get("ingredients")
    steps = strings(data.get("steps"), unique=False)
    tips = strings(data.get("tips"), unique=False)
    if not isinstance(rows, list) or not rows or not steps:
        raise Violation("incomplete", "The revised recipe has no ingredients or steps")
    revised: list[RevisedIngredient] = []
    for row in rows:
        name = row.get("name", "").strip() if isinstance(row, dict) else ""
        if not name:
            raise Violation("incomplete", "A revised ingredient has no name")
        if index.status(name, owned) == "unavailable":
            raise Violation("unavailable_ingredient", f"{name} is not among the owned ingredients")
        amount = row.get("amount")
        revised.append(
            RevisedIngredient(name=name, amount=amount.strip() or None if amount else None)
        )
    revised_keys = {_key(r.name) for r in revised}
    changes = _checked_changes(data.get("changes"), recipe)
    explained = {ref for c in changes for ref in c.ingredient_refs}
    for i, row in enumerate(recipe.ingredients, 1):
        if not _kept(row.name, revised_keys) and i not in explained:
            raise Violation("unexplained_change", "A dropped ingredient has no reason")
    source_keys = {_key(r.name) for r in recipe.ingredients}
    added = [r for r in revised if not _kept_in(r.name, source_keys)]
    if added and not changes:
        raise Violation("unexplained_change", "A new ingredient has no reason")
    gone = [
        _key(r.name)
        for r, s in zip(recipe.ingredients, status, strict=True)
        if s == "unavailable" and not _kept(r.name, revised_keys)
    ]
    for text in steps + tips:
        flat = _key(text)
        for name in gone:
            if len(name) >= 2 and name in flat and not any(name in k for k in revised_keys):
                raise Violation("mentions_unavailable", f"A step or tip mentions {name}")
    servings = data.get("servings")
    return (
        RevisedRecipe(
            servings=servings if isinstance(servings, int) and servings > 0 else None,
            ingredients=revised,
            steps=[RecipeStep(n=i, text=t) for i, t in enumerate(steps, 1)],
            tips=tips,
        ),
        changes,
    )


def _kept_in(name: str, source_keys: set[str]) -> bool:
    return bool(with_synonyms([_key(name)]) & source_keys)


def _checked_changes(raw: object, recipe: SourceRecipe) -> list[Change]:
    out: list[Change] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            raise Violation("bad_reference", "A change is not an object")
        reason = item.get("reason")
        ing = item.get("ingredient_refs")
        stp = item.get("step_refs")
        if not isinstance(reason, str) or not reason.strip():
            raise Violation("unexplained_change", "A change has no reason")
        if not (isinstance(ing, list) and isinstance(stp, list)):
            raise Violation("bad_reference", "A change has malformed references")
        n_ing, n_steps = len(recipe.ingredients), len(recipe.steps)
        if any(not isinstance(i, int) or not 1 <= i <= n_ing for i in ing) or any(
            not isinstance(i, int) or not 1 <= i <= n_steps for i in stp
        ):
            raise Violation("bad_reference", "A change points at a row or step that does not exist")
        out.append(Change(reason=reason.strip(), ingredient_refs=ing, step_refs=stp))
    return out
