// AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data.remote

import com.example.mylittlechef.model.Ingredient
import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Test

// JSON samples follow server/app/{vision,recipes}/schemas.py; a renamed field would turn into null here.
class ApiModelsTest {
    private val gson = Gson()

    @Test
    fun recommendResponse_mapsToRecipeWithServerMissingItems() {
        val json = """
            {"staples_assumed": ["소금"],
             "recipes": [{"id": 97, "name": "계란말이", "time_minutes": 30, "servings": 4,
                          "ingredients": ["계란", "다시마"], "steps": ["섞는다"], "missing": ["다시마"]}]}
        """

        val recipe = gson.fromJson(json, RecommendResponse::class.java).recipes.single().toRecipe()

        assertEquals(97L, recipe.id)
        assertEquals("계란말이", recipe.name)
        assertEquals(30, recipe.time)
        assertEquals(4, recipe.serving)
        assertEquals(listOf(Ingredient("계란"), Ingredient("다시마")), recipe.ingredients)
        assertEquals(listOf("섞는다"), recipe.steps)
        assertEquals(listOf(Ingredient("다시마")), recipe.missing)
    }

    @Test
    fun recipeWithoutTimeOrServings_defaultsToZero() {
        val json = """
            {"id": 1, "name": "양념장", "time_minutes": null, "servings": null,
             "ingredients": [], "steps": [], "missing": []}
        """

        val recipe = gson.fromJson(json, RecipeDto::class.java).toRecipe()

        assertEquals(0, recipe.time)
        assertEquals(0, recipe.serving)
    }

    @Test
    fun analyzeResponse_mapsCandidatesToIngredients() {
        val json = """
            {"candidates": [{"name": "다진마늘", "raw_texts": ["국산 다진마늘 500g"], "confidence": 1.0}]}
        """

        val response = gson.fromJson(json, AnalyzeResponse::class.java)

        assertEquals(listOf("국산 다진마늘 500g"), response.candidates.single().rawTexts)
        assertEquals(listOf(Ingredient("다진마늘")), response.candidates.map { it.toIngredient() })
    }
}
