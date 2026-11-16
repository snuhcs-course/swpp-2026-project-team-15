// Recipe image compatibility adapted with Codex, 2026-11-03; human review pending.
// AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; reviewed by Jaehyuk Choi.

// Ingredient catalog response added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
  
// Modified with Codex (GPT-6 Luna), 2026-11-03; reviewed by Ahyoon Choi.
// Changes: add mainImageUrl to RecipeDto

package com.example.mylittlechef.data.remote

import com.example.mylittlechef.model.Ingredient
import com.google.gson.annotations.SerializedName

// Field names mirror server/app/{vision,dishes}/schemas.py; a mismatch silently becomes null in Gson.

data class AnalyzeResponse(
    val candidates: List<IngredientCandidateDto>
)

data class IngredientCandidateDto(
    val name: String,
    @SerializedName("raw_texts") val rawTexts: List<String>,
    val confidence: Double
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

fun IngredientCandidateDto.toIngredient() = Ingredient(name = name)
