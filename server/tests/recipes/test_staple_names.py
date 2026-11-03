# AI-generated with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
"""The name-based endpoints read the same assumed-seasoning source as the id-based policy."""

from fastapi.testclient import TestClient

from app.main import create_app
from app.recipes.constants import STAPLE_SEASONINGS
from app.recipes.policy import RecommendationPolicy
from app.recipes.seasonings import (
    load_seasoning_policy,
    resolve_staple_names,
    seasoning_labelled_ids,
)
from app.recipes.service import RecipeRepository
from recipe_revision.seasoning import ASSUME_ALL, ASSUME_NONE, SeasoningPolicy
from tests.conftest import StubVision

# Ingredient ids of the shared test database (tests/conftest.py): 소금 5, 간장 4.
SALT, SOY = 5, 4


def listed(*pairs):
    return SeasoningPolicy("list", frozenset(i for i, _ in pairs), dict(pairs))


def test_names_follow_the_config_order_and_round_trip_to_the_same_ids(repository):
    catalog = repository.ingredient_catalog()
    policy = listed((SOY, "간장"), (SALT, "소금"))
    names = resolve_staple_names(policy, catalog)
    assert names == ("간장", "소금")
    assert {i for i, n in catalog.items() if n in names} == set(policy.assumed_ids)


def test_water_comes_first_and_modes_none_and_all_are_covered(integration_repository):
    # In the integration data 204 is "Water" and id 4 "Salt" is a seasoning in every recipe.
    catalog = integration_repository.ingredient_catalog()
    labelled = seasoning_labelled_ids(integration_repository.ingredient_labels())
    assert labelled == {4}
    assert resolve_staple_names(ASSUME_NONE, catalog) == ("Water",)
    assert resolve_staple_names(ASSUME_ALL, catalog, labelled) == ("Water", "Salt")
    both = listed((2, "Beta"), (4, "Salt"))
    assert resolve_staple_names(both, catalog) == ("Water", "Beta", "Salt")


def test_default_list_differs_from_the_legacy_names_only_by_the_pepper_spelling(real_catalog):
    names = resolve_staple_names(load_seasoning_policy({}), real_catalog)
    legacy = tuple("후추" if n == "후춧가루" else n for n in STAPLE_SEASONINGS)
    assert names == legacy
    assert set(names) ^ set(STAPLE_SEASONINGS) == {"후추", "후춧가루"}


def test_default_repository_keeps_the_legacy_names(repository):
    assert repository.staples == STAPLE_SEASONINGS


def missing_by_name(engine, staples):
    repo = RecipeRepository(engine, staples=staples)
    rows = repo.recommend(["밥", "계란", "대파"], max_missing=5, limit=5)
    return repo, {r.name: r.missing for r in rows}


def test_editing_the_list_moves_the_name_path_and_the_id_path_together(repository):
    engine = repository._engine
    catalog = repository.ingredient_catalog()
    sources, _ = repository.load_catalog([], 10)  # water is id 10 in this database
    fried_rice = next(s for s in sources if s.name == "계란볶음밥")
    available = frozenset({1, 2, 3})  # 밥, 계란, 대파; 간장 4 and 소금 5 are the rest

    for policy, expected_missing in (
        (listed((SALT, "소금")), ["간장"]),
        (listed((SALT, "소금"), (SOY, "간장")), []),
    ):
        names = resolve_staple_names(policy, catalog)
        _, by_name = missing_by_name(engine, names)
        counts = RecommendationPolicy(seasonings=policy, water_id=10).metrics(fried_rice, available)
        assert by_name["계란볶음밥"] == expected_missing
        assert counts.total_ingredients - counts.total_matches == len(expected_missing)


def test_assumed_staples_in_the_response_come_from_the_repository(repository):
    custom = RecipeRepository(repository._engine, staples=("물", "소금"))
    client = TestClient(create_app(StubVision(), custom))
    body = client.post("/recipes/recommend", json={"ingredients": ["밥", "계란"]}).json()
    assert body["staples_assumed"] == ["물", "소금"]
