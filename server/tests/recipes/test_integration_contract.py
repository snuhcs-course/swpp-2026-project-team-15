"""DTO and count projection tests independent of external providers."""
# AI-generated with Codex (GPT-6.1 Sol)
# 2026-10-17; reviewed by Soohyun An

import hashlib
import sqlite3
from dataclasses import replace

import pytest
from pydantic import ValidationError

from app.recipes.policy import RecommendationPolicy
from app.recipes.schemas import RecipeRevision, RecommendationsRequest
from app.recipes.service import SourceUnavailable, UnknownIngredients
from recipe_revision.models import SourceIngredient


@pytest.mark.parametrize(
    "body",
    [
        {"ingredient_ids": [0]},
        {"ingredient_ids": [-1]},
        {"ingredient_ids": [True]},
        {"ingredient_ids": ["1"]},
        {"ingredient_ids": [1.0]},
        *({"ingredient_ids": [], "revision_limit": limit} for limit in (0, 6, 3.0, "3", True)),
    ],
)
def test_strict_request_validation(body):
    with pytest.raises(ValidationError):
        RecommendationsRequest.model_validate(body)


def test_request_defaults_and_deduplication():
    request = RecommendationsRequest(ingredient_ids=[2, 1, 2])
    assert request.ingredient_ids == [2, 1]
    assert request.revision_limit == 3


@pytest.mark.parametrize(
    "value",
    [
        {"status": "failed"},
        {"status": "not_attempted"},
        {"status": "revised", "result": None},
        {
            "status": "refused",
            "result": {"can_revise": True, "reason": "", "changes": [], "revised_recipe": None},
        },
        {
            "status": "not_attempted",
            "not_attempted_reason": "outside_revision_limit",
            "result": {
                "can_revise": False,
                "reason": "Refused",
                "changes": [],
                "revised_recipe": None,
            },
        },
    ],
)
def test_inconsistent_outcomes_rejected(value):
    with pytest.raises(ValidationError):
        RecipeRevision.model_validate(value)


def test_catalog_source_and_inventory_are_read_only(integration_repository, integration_db):
    before = hashlib.sha256(integration_db.read_bytes()).digest()
    recipes, inventory = integration_repository.load_catalog([1, 1, 4, 204], 204)
    assert len(recipes) == 9
    assert [row.ingredient_id for row in inventory] == [1, 4, 204]
    source = next(row for row in recipes if row.recipe_id == 20)
    assert len(source.ingredients) == 5
    assert source.servings == "4 servings"
    assert source.description == "Source context"
    assert source.ingredients[0].quantity_text is None
    assert source.ingredients[0].original_name == "Raw label"
    assert [step.instruction for step in source.steps] == ["First", "Second"]
    assert [step.tip for step in source.steps] == [None, "Source tip"]
    assert hashlib.sha256(integration_db.read_bytes()).digest() == before


def test_missing_catalog_data(integration_repository, integration_db):
    with pytest.raises(UnknownIngredients):
        integration_repository.load_catalog([999], 204)
    with pytest.raises(SourceUnavailable):
        integration_repository.load_catalog([1], 999)
    with sqlite3.connect(integration_db) as db:
        db.execute("DELETE FROM recipe_step WHERE recipe_id=10")
    with pytest.raises(SourceUnavailable):
        integration_repository.load_catalog([1], 204)


def test_database_query_failure_is_sanitized(integration_repository, integration_db):
    with sqlite3.connect(integration_db) as db:
        db.execute("DROP TABLE recipe_step")
    with pytest.raises(SourceUnavailable, match="Recipe database is unavailable"):
        integration_repository.load_catalog([1], 204)


def test_projection_excludes_water_and_resolved_seasonings(integration_repository):
    recipes, _ = integration_repository.load_catalog([1, 2], 204)
    policy = RecommendationPolicy()
    counts = {row.recipe_id: policy.metrics(row, frozenset({1, 2, 204})) for row in recipes}
    assert counts[20].general_matches == 2
    assert counts[20].total_ingredients == counts[20].total_matches == 2
    assert policy.accepts(counts[20])  # General-match branch.
    assert policy.accepts(counts[30])  # Main-match branch.
    assert counts[10].total_ingredients == 2  # Unknown Gamma remains in ranking totals.
    assert counts[10].total_matches == 1
    assert not policy.accepts(counts[60])
    assert not policy.accepts(counts[80])
    assert counts[60].total_ingredients == 0
    assert RecommendationPolicy(rule_id="B").accepts(counts[80])
    assert not RecommendationPolicy(general_minimum=3, main_minimum=2).accepts(counts[20])
    # A main/seasoning conflict retains the existing main-first resolution.
    conflict = replace(
        recipes[2],
        ingredients=(
            *recipes[2].ingredients,
            SourceIngredient(999, 1, "Alpha", None, "3060003", None, None),
        ),
    )
    assert policy.metrics(conflict, frozenset({1})).main_matches == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"rule_id": "missing"},
        {"general_minimum": 0},
        {"main_minimum": 0},
        {"water_id": 0},
        {"default_revision_limit": 6},
        {"maximum_revision_limit": 2},
    ],
)
def test_invalid_policy_rejected(kwargs):
    with pytest.raises(ValueError):
        RecommendationPolicy(**kwargs)
