"""AI-assisted HE regressions, 2026-11-10; human review pending. No paid calls."""

import sqlite3

from app.recipes.constants import with_synonyms
from tests.conftest import StubVision


def test_normalizes_spaces_and_supports_only_forward_preparation():
    assert {"마늘", "다진마늘"} <= with_synonyms([" 마 늘 "])
    assert {"대파", "다진파"} <= with_synonyms(["대 파"])
    assert "마늘" not in with_synonyms(["다진 마늘"])
    assert "대파" not in with_synonyms(["다진 파"])
    assert {"계란", "달걀"} <= with_synonyms(["달 걀"])
    assert "양배추" not in with_synonyms(["배추"])


def test_id_inventory_expands_the_same_preparation_rules(integration_db, integration_repository):
    with sqlite3.connect(integration_db) as db:
        db.executemany("INSERT INTO ingredient VALUES (?,?)", [(301, "마늘"), (302, "다진 마늘")])
    _, forward = integration_repository.load_catalog([301], 204)
    _, reverse = integration_repository.load_catalog([302], 204)
    assert {301, 302, 204} == {item.ingredient_id for item in forward}
    assert 301 not in {item.ingredient_id for item in reverse}


def test_explore_is_additive_searches_beyond_fridge_and_does_not_repeat(make_client):
    client = make_client(StubVision())
    assert client.get("/recipes/explore/capabilities").json().get("search_supported") is True
    first = client.post(
        "/recipes/explore", json={"ingredients": ["밥", "계란", "대파"], "limit": 1}
    )
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["recipes"][0]["name"] == "계란볶음밥"
    search = client.post("/recipes/explore", json={"ingredients": [], "query": "김치", "limit": 1})
    assert search.status_code == 200
    assert search.json()["recipes"][0]["name"] == "김치찌개"
    assert "김치" in search.json()["recipes"][0]["missing"]
    end = client.post(
        "/recipes/explore", json={"ingredients": [], "query": "김치", "seen_ids": [2]}
    )
    assert end.json()["recipes"] == [] and end.json()["has_more"] is False


def test_unknown_names_are_reported_and_catalog_has_stable_ids(make_client):
    client = make_client(StubVision())
    response = client.post("/recipes/explore", json={"ingredients": ["미등록 두푸", "계란"]})
    assert response.status_code == 200
    assert response.json()["unregistered"][0]["name"] == "미등록 두푸"
    catalog = client.get("/recipes/explore/catalog")
    assert catalog.status_code == 200
    assert {"ingredient_id": 2, "name": "계란"} in catalog.json()["items"]


def test_manufacturing_exclusion_is_exact_and_applies_to_legacy_and_ai_sources(
    recipe_db, repository
):
    with sqlite3.connect(recipe_db) as db:
        db.execute("UPDATE recipe SET name='된장' WHERE recipe_id=1")
        db.execute("UPDATE recipe SET name='된장찌개' WHERE recipe_id=2")
    assert all(r.name != "된장" for r in repository.recommend(["밥", "계란", "대파"], 5, 100))
    sources, _ = repository.load_catalog([], 10)
    assert "된장" not in {r.name for r in sources}
    assert "된장찌개" in {r.name for r in sources}


def test_suggestions_keep_spaced_display_names_and_ignore_manufacturing(recipe_db, repository):
    with sqlite3.connect(recipe_db) as db:
        db.execute("UPDATE ingredient SET name='다진 파' WHERE ingredient_id=3")
        db.execute("UPDATE recipe SET name='된장' WHERE recipe_id=2")
    suggestions = repository.ingredient_suggestions(["밥", "계란"], min_recipe_count=1, limit=100)
    assert "다진 파" in {row.name for row in suggestions}
    assert not any("된장" in row.ready_recipe_names for row in suggestions)
