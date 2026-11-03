// AI-assisted with Codex, 2026-11-01; human review pending.
package com.example.mylittlechef.data.remote

import com.google.gson.annotations.SerializedName
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import retrofit2.http.*

interface OnDemandRecipeApi {
    @GET("recipes/ingredient-catalog") suspend fun recipeCatalog(): RecipeCatalogDto
    @POST("recipes/candidates") suspend fun candidates(@Body request: InventoryIdsDto): CandidatesDto
    @POST("recipes/{id}/revision") suspend fun reviseRecipe(@Path("id") id: Long, @Body request: InventoryIdsDto): SingleRevisionDto
}
interface FullRecipeApi : IngredientSupportApi, OnDemandRecipeApi

data class CatalogItemDto(@SerializedName("ingredient_id") val id: Int, val name: String, val aliases: List<String>)
data class RecipeCatalogDto(val items: List<CatalogItemDto>)
data class InventoryIdsDto(@SerializedName("ingredient_ids") val ids: List<Int>)
data class SourceIngredientDto(@SerializedName("ingredient_id") val id: Int, val name: String, @SerializedName("quantity_text") val quantity: String?)
data class SourceStepDto(@SerializedName("step_number") val number: Int, val instruction: String)
data class SourceRecipeDto(@SerializedName("recipe_id") val id: Long, val name: String,
    @SerializedName("cooking_time") val time: String?, val servings: String?,
    val ingredients: List<SourceIngredientDto>, val steps: List<SourceStepDto>)
data class CandidateDto(@SerializedName("recipe_id") val id: Long, val original: SourceRecipeDto,
    @SerializedName("missing_ingredients") val missing: List<SourceIngredientDto>,
    @SerializedName("revision_candidate") val revisionCandidate: Boolean,
    @SerializedName("assumed_ingredient_ids") val assumedIds: List<Int>? = null)
data class CandidatesDto(val recipes: List<CandidateDto>, @SerializedName("assumed_ingredient_ids") val assumedIds: List<Int> = emptyList())
data class RevisedRecipeDto(val name: String, val servings: String?, val ingredients: List<SourceIngredientDto>, val steps: List<SourceStepDto>)
data class RevisionChangeDto(val kind: String, val reason: String)
data class RevisionResultDto(val reason: String, val changes: List<RevisionChangeDto>, @SerializedName("revised_recipe") val recipe: RevisedRecipeDto?)
data class RevisionErrorDto(val code: String)
data class RevisionOutcomeDto(val status: String, val result: RevisionResultDto?, val error: RevisionErrorDto?)
data class SingleRevisionDto(@SerializedName("recipe_id") val id: Long, val original: SourceRecipeDto,
    val revision: RevisionOutcomeDto,
    @SerializedName("assumed_ingredient_ids") val assumedIds: List<Int>? = null)

fun SourceRecipeDto.toOriginal(missing: List<SourceIngredientDto>, candidate: Boolean) = Recipe(
    id, name, Regex("\\d+").find(time.orEmpty())?.value?.toIntOrNull() ?: 0,
    Regex("\\d+").find(servings.orEmpty())?.value?.toIntOrNull() ?: 0,
    ingredients.map { Ingredient(it.name) }, steps.sortedBy { it.number }.map { it.instruction },
    missing = missing.map { Ingredient(it.name) }, servingText = servings,
    ingredientQuantities = ingredients.map { it.quantity }, revisionCandidate = candidate)
