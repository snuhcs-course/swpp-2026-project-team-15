// AI-assisted selected recipe contract, 2026-11-10; human review pending.
package com.example.mylittlechef.data.remote

import com.google.gson.annotations.SerializedName
import retrofit2.http.*

interface SelectedRecipeApi {
    @GET("recipes/revision-capabilities") suspend fun selectedCapabilities(): SelectedCapabilities
    @POST("recipes/{id}/revision") suspend fun reviseSelected(@Path("id") id: Long,
        @Body request: SelectedRevisionRequest): SelectedRevisionResponse
}
data class SelectedCapabilities(@SerializedName("selected_recipe_supported") val supported: Boolean,
    @SerializedName("provider_mode") val mode: String = "unknown")
data class SelectedRevisionRequest(val ingredients: List<String>,
    @SerializedName("ignore_unregistered") val ignoreUnregistered: Boolean = false)
data class SelectedRevisionResponse(@SerializedName("recipe_id") val id: Long,
    val original: SourceRecipeDto,
    @SerializedName("original_missing") val missing: List<SourceIngredientDto>,
    val revision: RevisionOutcomeDto,
    @SerializedName("provider_mode") val mode: String = "unknown",
    @SerializedName("main_image_url") val imageUrl: String? = null)
