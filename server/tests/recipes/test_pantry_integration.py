# AI-assisted integration with Codex, 2026-10-29; human review pending.
"""Regression checks for restored client catalog and ingredient suggestions."""
from app.recipes.service import RecipeRepository
from tests.conftest import StubVision


def test_catalog_contains_sorted_unique_source_names(repository: RecipeRepository):
    names = repository.ingredient_names()
    assert names == sorted(set(names))
    assert {"두부", "계란", "대파"} <= set(names)


def test_suggestions_rank_new_ready_recipes_before_frequency(repository: RecipeRepository):
    results = repository.ingredient_suggestions(["김치", "두부"], min_recipe_count=1)
    assert results[0].name == "돼지고기"
    assert results[0].ready_recipe_count == 1
    assert results[0].ready_recipe_names == ["김치찌개"]
    assert all(item.name not in {"김치", "두부", "소금", "물"} for item in results)


def test_owned_alias_is_not_suggested_again(repository: RecipeRepository):
    results = repository.ingredient_suggestions(["달걀"], min_recipe_count=1)
    assert not {"계란", "달걀"} & {item.name for item in results}


def test_new_endpoints_leave_legacy_recommendation_available(make_client):
    client = make_client(StubVision())
    catalog = client.get("/recipes/ingredients")
    assert catalog.status_code == 200
    assert "두부" in catalog.json()["names"]
    suggestions = client.post("/recipes/ingredient-suggestions", json={"ingredients": ["두부"]})
    assert suggestions.status_code == 200
    assert isinstance(suggestions.json()["suggestions"], list)
    assert client.post("/recipes/recommend", json={"ingredients": ["두부"]}).status_code == 200


def test_prepared_form_does_not_hide_or_mislabel_base_ingredient(recipe_db):
    import sqlite3
    from app.database import read_only_sqlite_engine
    with sqlite3.connect(recipe_db) as db:
        db.execute("INSERT INTO ingredient VALUES (14, '다진파')")
        for recipe_id, ingredient_id in [(100, 14), (101, 14), (102, 14), (103, 3)]:
            db.execute("INSERT INTO recipe (recipe_id, name) VALUES (?, ?)", (recipe_id, f"파 요리 {recipe_id}"))
            db.executemany("INSERT INTO recipe_ingredient(recipe_id, ingredient_id, ingredient_type_code) VALUES (?, ?, '3060001')",
                           [(recipe_id, ingredient_id), (recipe_id, 8)])
    engine = read_only_sqlite_engine(recipe_db)
    try:
        repository = RecipeRepository(engine)
        whole = next(x for x in repository.ingredient_suggestions(["두부"], min_recipe_count=1) if x.name == "대파")
        assert whole.ready_recipe_count == 4
        assert whole.recipe_count == 5
        assert all(x.name != "다진파" for x in repository.ingredient_suggestions(["두부"], min_recipe_count=1))
        added = next(x for x in repository.ingredient_suggestions(["두부", "다진파"], min_recipe_count=1) if x.name == "대파")
        assert added.ready_recipe_count == 1
        assert added.ready_recipe_names == ["파 요리 103"]
    finally:
        engine.dispose()
