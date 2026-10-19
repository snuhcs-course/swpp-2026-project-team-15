package com.example.mylittlechef.domain

import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import org.junit.Assert.assertEquals
import org.junit.Test

class RecipeSorterTest {
    private fun recipe(id: Long, time: Int, missing: List<String>? = null) = Recipe(
        id = id, name = "recipe$id", time = time, serving = 1,
        ingredients = listOf(Ingredient("두부"), Ingredient("김치")),
        steps = emptyList(), missing = missing?.map(::Ingredient)
    )

    @Test fun recommended_keepsServerOrder() {
        val input = listOf(recipe(3, 20), recipe(1, 5), recipe(2, 10))
        assertEquals(listOf(3L, 1L, 2L), sortRecipes(input, RecipeSortType.RECOMMENDED).map { it.id })
    }

    @Test fun cookingTime_putsUnknownLastAndPreservesTies() {
        val input = listOf(recipe(1, 0), recipe(2, 15), recipe(3, 5), recipe(4, 15))
        assertEquals(listOf(3L, 2L, 4L, 1L), sortRecipes(input, RecipeSortType.COOKING_TIME).map { it.id })
    }

    @Test fun missingCount_usesServerMissingAndPreservesTies() {
        val input = listOf(recipe(1, 8, listOf("a", "b")), recipe(2, 8, emptyList()), recipe(3, 8, listOf("c")))
        assertEquals(listOf(2L, 3L, 1L), sortRecipes(input, RecipeSortType.FEWEST_MISSING).map { it.id })
    }

    @Test fun missingCount_fallsBackToFridgeForLocalRecipes() {
        val input = listOf(recipe(1, 8), recipe(2, 8, emptyList()))
        assertEquals(listOf(2L, 1L), sortRecipes(input, RecipeSortType.FEWEST_MISSING, listOf("두부")).map { it.id })
    }

    @Test fun missingCount_usesCookingTimeThenServerOrderForTies() {
        val input = listOf(
            recipe(1, 30, listOf("양파")),
            recipe(2, 50, emptyList()),
            recipe(3, 10, listOf("양파")),
            recipe(4, 0, listOf("양파")),
            recipe(5, 10, listOf("양파"))
        )
        assertEquals(listOf(2L, 3L, 5L, 1L, 4L),
            sortRecipes(input, RecipeSortType.FEWEST_MISSING).map { it.id })
    }
}
