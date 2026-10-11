# AI-generated with Claude Code (Opus 5.5), 2026-10-11; review pending by Jaehyuk Choi.
from app.recipes import RecipeRepository
from app.vocabulary import with_synonyms


def names(recipes) -> list[str]:
    return [recipe.name for recipe in recipes]


def test_recipe_ready_when_fridge_and_staples_cover_everything(repository: RecipeRepository):
    [recipe] = repository.recommend(["밥", "계란", "대파"], max_missing=0, limit=10)

    assert recipe.name == "계란볶음밥"
    assert recipe.missing == []
    assert recipe.time_minutes == 10
    assert recipe.servings == 1
    assert recipe.steps == ["계란볶음밥 1단계", "계란볶음밥 2단계"]


def test_synonym_in_fridge_matches_recipe_ingredient(repository: RecipeRepository):
    assert names(repository.recommend(["밥", "달걀", "대파"], max_missing=0, limit=10)) == [
        "계란볶음밥"
    ]


def test_one_missing_ingredient_is_reported(repository: RecipeRepository):
    [recipe] = repository.recommend(["김치", "두부"], max_missing=1, limit=10)

    assert recipe.name == "김치찌개"
    assert recipe.missing == ["돼지고기"]


def test_recipes_beyond_missing_limit_are_excluded(repository: RecipeRepository):
    assert repository.recommend(["김치", "두부"], max_missing=0, limit=10) == []


def test_ready_recipes_rank_before_incomplete_ones(repository: RecipeRepository):
    result = repository.recommend(["밥", "계란", "대파", "김치", "두부"], max_missing=1, limit=10)

    assert names(result) == ["계란볶음밥", "김치찌개"]


def test_staples_alone_do_not_produce_recommendations(repository: RecipeRepository):
    assert repository.recommend([], max_missing=3, limit=10) == []
    assert "만능 양념장" not in names(repository.recommend(["간장"], max_missing=3, limit=10))


def test_unknown_ingredients_are_ignored(repository: RecipeRepository):
    assert repository.recommend(["드래곤후르츠"], max_missing=1, limit=10) == []


def test_limit_caps_result_count(repository: RecipeRepository):
    result = repository.recommend(["밥", "계란", "대파", "김치", "두부"], max_missing=1, limit=1)

    assert names(result) == ["계란볶음밥"]


def test_owned_ingredient_covers_its_prepared_form():
    assert {"대파", "다진파"} <= with_synonyms(["대파"])
    assert "대파" not in with_synonyms(["다진파"])
