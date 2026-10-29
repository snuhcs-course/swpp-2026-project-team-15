// AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; reviewed by Jaehyuk Choi.
// Ingredient catalog response added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
package com.example.mylittlechef.data.remote

import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import com.google.gson.annotations.SerializedName

// Field names mirror server/app/{vision,recipes}/schemas.py; a mismatch silently becomes null in Gson.

data class AnalyzeResponse(
    val candidates: List<IngredientCandidateDto>
)

data class IngredientCandidateDto(
    val name: String,
    @SerializedName("raw_texts") val rawTexts: List<String>,
    val confidence: Double
)

data class RecommendRequest(
    val ingredients: List<String>
)

data class RecommendResponse(
    @SerializedName("staples_assumed") val staplesAssumed: List<String>,
    val recipes: List<RecipeDto>
)

// Ingredient suggestions added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
data class IngredientSuggestionRequest(
    val ingredients: List<String>
)

data class IngredientSuggestionDto(
    val name: String,
    @SerializedName("ready_recipe_count") val readyRecipeCount: Int,
    @SerializedName("recipe_count") val recipeCount: Int,
    @SerializedName("ready_recipe_names") val readyRecipeNames: List<String>
)

data class IngredientSuggestionResponse(
    val suggestions: List<IngredientSuggestionDto>
)

data class IngredientCatalogResponse(
    val names: List<String>
)

data class RecipeDto(
    val id: Long,
    val name: String,
    @SerializedName("time_minutes") val timeMinutes: Int?,
    val servings: Int?,
    val ingredients: List<String>,
    val steps: List<String>,
    val missing: List<String>
)

fun IngredientCandidateDto.toIngredient() = Ingredient(name = name)

fun RecipeDto.toRecipe() = Recipe(
    id = id,
    name = name,
    time = timeMinutes ?: 0,
    serving = servings ?: 0,
    ingredients = ingredients.map(::Ingredient),
    steps = steps,
    missing = missing.map(::Ingredient)
)
