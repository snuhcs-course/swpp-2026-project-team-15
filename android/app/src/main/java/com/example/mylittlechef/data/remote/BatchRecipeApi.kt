// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.data.remote

import com.google.gson.annotations.SerializedName
import retrofit2.http.Body
import retrofit2.http.POST

/** Deployed main contract: server chooses recipes, not a client-selected recipe ID. */
interface BatchRecipeApi {
    @POST("recipes/recommendations")
    suspend fun recommendations(@Body request: BatchRevisionRequest): BatchRecommendationsDto
}

interface DeployedRecipeApi : IngredientSupportApi, BatchRecipeApi

data class BatchRevisionRequest(
    @SerializedName("ingredient_ids") val ids: List<Int>,
    @SerializedName("revision_limit") val revisionLimit: Int = 1
)
data class BatchRecipeEntryDto(
    @SerializedName("recipe_id") val id: Long,
    val original: SourceRecipeDto,
    val revision: RevisionOutcomeDto,
    @SerializedName("main_image_url") val mainImageUrl: String? = null
)
data class BatchSummaryDto(
    val limit: Int,
    @SerializedName("selected_count") val selectedCount: Int,
    @SerializedName("attempted_count") val attemptedCount: Int,
    @SerializedName("stopped_error") val stoppedError: RevisionErrorDto?
)
data class BatchRecommendationsDto(
    val recipes: List<BatchRecipeEntryDto>,
    @SerializedName("assumed_ingredient_ids") val assumedIds: List<Int>,
    @SerializedName("revision_summary") val summary: BatchSummaryDto
)
