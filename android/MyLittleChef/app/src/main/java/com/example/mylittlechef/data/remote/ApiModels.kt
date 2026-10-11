// AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data.remote

import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import com.google.gson.annotations.SerializedName

// Field names mirror server/app/schemas.py; a mismatch silently becomes null in Gson.

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
