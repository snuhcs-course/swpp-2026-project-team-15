# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""The rules a revised recipe must obey, checked without a model call.

A result that uses an unavailable ingredient, mentions a dropped one in a step or tip, points at
a row or step that does not exist, or changes the recipe without a reason raises ``Violation``;
the caller reports it as a failure and never repairs it silently.
"""

# ruff: noqa: E501

import re

from app.dishes.answers import strings
from app.dishes.korean import attach
from app.dishes.roles import Availability
from app.dishes.schemas import Change, RecipeStep, RevisedIngredient, RevisedRecipe, SourceRecipe
from app.dishes.synonyms import with_synonyms

# Particles that may follow a one-character ingredient name in a step ("밥을 넣고", "밥으로").
# The two-syllable ones were missing until the server review (2026-11-19).
_PARTICLES = (
    "으로", "이랑", "에서", "까지", "부터", "하고", "처럼", "보다",
    "을", "를", "이", "가", "은", "는", "과", "와", "도", "에", "만", "의", "로", "랑",
)  # fmt: skip
_TAIL = "|".join(_PARTICLES)


class RefusalNeeded(Exception):
    """The answer revises a recipe that should have been refused (a main ingredient is gone)."""

    def __init__(self, name: str):
        super().__init__(name)
        self.name = name
        self.reason = f"{attach(name, '이')} 없으면 이 요리가 되지 않아요."


class Violation(Exception):
    """The model's answer breaks a rule of the check (code is machine readable)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _key(text: str) -> str:
    return text.strip().replace(" ", "")


def mentions(text: str, name: str, kept: set[str] | frozenset[str] = frozenset()) -> bool:
    """Whether ``text`` names the ingredient by any of its synonyms (계란/달걀).

    Names of two or more characters match anywhere (spaces ignored); a one-character name (밥,
    김, 파) only as a word of its own, optionally followed by a particle, so that 김치 does not
    count as 김 and 대파 or 파프리카 not as 파. The ``kept`` names are blanked out first, longest
    first, so a kept 고추장 does not count as a mention of a removed 고추. Only kept names that
    contain the removed name are blanked: a kept 오일 must not hide a removed 올리브 오일."""
    kept_forms = {f for k in kept for f in with_synonyms([_key(k)])}
    for form in with_synonyms([_key(name)]):
        if not form:
            continue
        spaced, flat = text, _key(text)
        for other in sorted((k for k in kept_forms if form in k and k != form), key=len)[::-1]:
            spaced = spaced.replace(other, "□" * len(other))
            flat = flat.replace(other, "□" * len(other))
        if len(form) >= 2 and form in flat:
            return True
        word = rf"(?<![가-힣]){re.escape(form)}(?:{_TAIL})?(?![가-힣])"
        if len(form) == 1 and re.search(word, spaced):
            return True
    return False


def identity_missing(dish_name: str, recipe: SourceRecipe, status: list[str]) -> list[str]:
    """Unavailable recipe ingredients that the dish is named after, in recipe order.

    A name of two or more characters counts when it (or a synonym) occurs in the dish name; a
    one-character name only when the dish name ends with it, because a Korean dish name ends in
    its head (김치볶음밥 -> 밥) while a leading syllable is often part of another word (김치)."""
    dish = _key(dish_name)
    out: list[str] = []
    for row, s in zip(recipe.ingredients, status, strict=True):
        if s != "unavailable":
            continue
        forms = [f for f in with_synonyms([_key(row.name)]) if f]
        named = any(
            (len(f) >= 2 and f in dish) or (len(f) == 1 and dish.endswith(f)) for f in forms
        )
        if named and row.name not in out:
            out.append(row.name)
    return out


def check_main_kept(
    recipe: SourceRecipe,
    status: list[str],
    revised: RevisedRecipe,
    changes: list[Change],
) -> None:
    """Every main ingredient stays, or an unavailable one is replaced in a change that names it.

    Raises RefusalNeeded when an unavailable main ingredient is dropped without a replacement
    (the dish cannot be made) and Violation when an available one is dropped."""
    revised_keys = {_key(r.name) for r in revised.ingredients}
    source_keys = {_key(r.name) for r in recipe.ingredients}
    added = any(not _kept_in(r.name, source_keys) for r in revised.ingredients)
    named = {ref for c in changes for ref in c.ingredient_refs}
    for i, (row, s) in enumerate(zip(recipe.ingredients, status, strict=True), 1):
        if row.role != "main" or _kept(row.name, revised_keys):
            continue
        if s != "unavailable":
            raise Violation("main_dropped", f"The main ingredient {row.name} was dropped")
        if not (added and i in named):
            raise RefusalNeeded(row.name)


def check_short_mentions(recipe: SourceRecipe, status: list[str], revised: RevisedRecipe) -> None:
    """Raise Violation when a step or tip still names a removed one-character ingredient (밥, 김);
    ``check`` covers the longer names."""
    revised_keys = {_key(r.name) for r in revised.ingredients}
    for row, s in zip(recipe.ingredients, status, strict=True):
        name = _key(row.name)
        if s != "unavailable" or len(name) != 1 or _kept(name, revised_keys):
            continue
        texts = [step.text for step in revised.steps] + revised.tips
        if any(mentions(t, name, revised_keys) for t in texts):
            raise Violation("mentions_unavailable", f"A step or tip mentions {name}")


def _kept(name: str, revised_keys: set[str]) -> bool:
    return bool(with_synonyms([_key(name)]) & revised_keys)


def check(
    data: dict,
    recipe: SourceRecipe,
    status: list[str],
    index: Availability,
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
        # A provider that does not enforce the schema may send null or a number here.
        name = row.get("name") if isinstance(row, dict) else None
        if not isinstance(name, str) or not name.strip():
            raise Violation("incomplete", "A revised ingredient has no name")
        name = name.strip()
        if index.status(name, owned) == "unavailable":
            raise Violation("unavailable_ingredient", f"{name} is not among the owned ingredients")
        amount = row.get("amount")
        if amount is not None and not isinstance(amount, str):
            raise Violation("incomplete", "A revised amount is not text")
        revised.append(RevisedIngredient(name=name, amount=(amount or "").strip() or None))
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
        for name in gone:
            if len(name) >= 2 and mentions(text, name, revised_keys):
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
