package com.example.mylittlechef.domain

import com.example.mylittlechef.model.Recipe

enum class RecipeSortType(val label: String) {
    RECOMMENDED("추천순"),
    COOKING_TIME("조리시간 짧은 순"),
    FEWEST_MISSING("부족한 재료 적은 순")
}

fun sortRecipes(
    recipes: List<Recipe>,
    type: RecipeSortType,
    fridgeNames: List<String> = emptyList()
): List<Recipe> {
    if (type == RecipeSortType.RECOMMENDED) return recipes.toList()
    val available = fridgeNames.map { it.trim().lowercase() }.toSet()
    fun missingCount(recipe: Recipe): Int =
        recipe.missing?.size ?: recipe.ingredients.count { it.name.trim().lowercase() !in available }
    val indexed = recipes.withIndex()
    val sorted = when (type) {
        RecipeSortType.RECOMMENDED -> indexed
        RecipeSortType.COOKING_TIME -> indexed.sortedWith(
            compareBy<IndexedValue<Recipe>> { if (it.value.time <= 0) Int.MAX_VALUE else it.value.time }
                .thenBy { it.index }
        )
        RecipeSortType.FEWEST_MISSING -> indexed.sortedWith(
            compareBy<IndexedValue<Recipe>> { missingCount(it.value) }.thenBy { it.index }
        )
    }
    return sorted.map { it.value }
}
