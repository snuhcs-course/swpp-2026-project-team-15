# AI-generated with Claude Code (Sonnet 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
"""Contracts of the dish list, the ingredient index and the recipe book."""

from app.dishes.catalog import Catalog, Dish
from app.dishes.recipe_names import RecipeNames
from app.dishes.recipes import CreditedRecipes, RecipeStore
from app.dishes.schemas import SourceRecipe
from tests.dishes.contracts.fakes import (
    FakeCatalog,
    FakeIngredientIndex,
    FakeRecipeBook,
    FakeVideoVerifier,
)
from tests.dishes.test_revision import RECIPE

DISH = Dish(
    id="kimchi-fried-rice",
    name="김치볶음밥",
    category="볶음밥",
    key_ingredients=("밥", "김치"),
    optional=frozenset(),
    aliases=(),
)


class DishCatalogContract:
    def make(self):
        raise NotImplementedError

    def test_lookup_by_id_and_by_name_agree(self):
        catalog = self.make()
        dish = catalog.get("kimchi-fried-rice")
        assert dish is not None and catalog.by_name(dish.name) == dish

    def test_unknown_dish_is_none(self):
        catalog = self.make()
        assert catalog.get("nope") is None and catalog.by_name("없는 요리") is None

    def test_all_matches_the_length(self):
        catalog = self.make()
        assert len(catalog) == len(catalog.all()) >= 1


class TestFakeCatalog(DishCatalogContract):
    def make(self):
        return FakeCatalog([DISH])


class TestCatalog(DishCatalogContract):
    def make(self):
        return Catalog.load()


class AvailabilityContract:
    def make(self):
        raise NotImplementedError

    def test_owned_ingredient_is_not_unavailable(self):
        index = self.make()
        owned = index.owned(["김치"])
        assert index.status("김치", owned) in {"owned", "assumed"}

    def test_status_is_one_of_three_words(self):
        index = self.make()
        assert index.status("zzz", index.owned([])) in {"owned", "assumed", "unavailable"}


class TestRecipeNamesAsAvailability(AvailabilityContract):
    def make(self):
        return RecipeNames.load()


class IngredientIndexContract(AvailabilityContract):
    def test_names_are_unique_and_additions_respect_the_limit(self):
        index = self.make()
        names = index.ingredient_names()
        assert names and len(set(names)) == len(names)
        assert len(index.additions(["밥"], limit=2)) <= 2


class TestFakeIngredientIndex(IngredientIndexContract):
    def make(self):
        return FakeIngredientIndex()


class TestCatalogAsIngredientIndex(IngredientIndexContract):
    def make(self):
        return Catalog.load()


class RecipeBookContract:
    def make(self):
        raise NotImplementedError

    def test_known_dish_has_its_recipe(self):
        book = self.make()
        recipe = book.get("kimchi-fried-rice")
        assert recipe is not None and recipe.dish_id == "kimchi-fried-rice"
        assert "kimchi-fried-rice" in book

    def test_unknown_dish_has_none(self):
        book = self.make()
        assert book.get("nope") is None and "nope" not in book


class TestFakeRecipeBook(RecipeBookContract):
    def make(self):
        return FakeRecipeBook({"kimchi-fried-rice": SourceRecipe.model_validate(RECIPE)})


class TestRecipeStore(RecipeBookContract):
    def make(self):
        return RecipeStore({"kimchi-fried-rice": SourceRecipe.model_validate(RECIPE)})


class TestCreditedRecipes(RecipeBookContract):
    def make(self):
        store = RecipeStore({"kimchi-fried-rice": SourceRecipe.model_validate(RECIPE)})
        return CreditedRecipes(store, FakeVideoVerifier({"abcdefghijk"}))
