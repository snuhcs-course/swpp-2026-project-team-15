# AI-assisted with Codex, 2026-11-21; reviewed by Soohyun An
"""Synonym-aware explanation-reference coverage for a terminal revising answer."""

from experiments.dish_revision.scoring import dropped_ingredients

from app.dishes.schemas import SourceRecipe

from .contract import Rate, SourceRecipeSnapshot


def deleted_ingredient_coverage(recipe: SourceRecipe | SourceRecipeSnapshot, answer: dict) -> Rate:
    """Count dropped source rows named by at least one valid ingredient reference.

    The caller supplies the terminal revising answer, never an earlier rejected
    answer or a refusal. Ingredient rows must have string names so absent/malformed
    data cannot be mistaken for a recipe that deleted every source ingredient.
    As in the existing research metric, coverage measures reference presence, not
    reason quality, change-kind validity, or production acceptance.
    """
    if not isinstance(answer, dict) or answer.get("can_revise") is not True:
        raise ValueError("coverage requires a terminal revising answer")
    rows = answer.get("ingredients")
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) or not isinstance(row.get("name"), str) for row in rows
    ):
        raise ValueError("coverage requires ingredient rows with string names")
    # Focused compatibility tests pin this helper's synonym/spacing semantics.
    # Its historical ingredient_coverage wrapper is not reused because it treats
    # bool as int when collecting refs; v1 must only count real source row IDs.
    dropped = dropped_ingredients(recipe, answer)
    named: set[int] = set()
    changes = answer.get("changes")
    for change in changes if isinstance(changes, list) else []:
        refs = change.get("ingredient_refs") if isinstance(change, dict) else None
        if not isinstance(refs, list):
            continue
        named.update(
            ref for ref in refs if type(ref) is int and 1 <= ref <= len(recipe.ingredients)
        )
    covered = sum(row in named for row in dropped)
    total = len(dropped)
    # Zero deleted rows is explicitly inapplicable in the frozen Rate contract,
    # represented by counts 0/0 with a null value rather than zero or full coverage.
    return Rate(numerator=covered, denominator=total, value=covered / total if total else None)
