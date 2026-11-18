// AI-assisted additive HE recognition review contract, 2026-11-09; manual review pending.
package com.example.mylittlechef.data.remote

import com.google.gson.annotations.SerializedName
import okhttp3.MultipartBody
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import com.example.mylittlechef.domain.PhotoAnalysis
import com.example.mylittlechef.domain.RecognitionMode
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.RecognitionEvidence

interface RecognitionReviewApi {
    @GET("vision/capabilities")
    suspend fun capabilities(): RecognitionCapabilitiesDto

    @Multipart @POST("analyze/review")
    suspend fun analyzePhoto(@Part image: MultipartBody.Part): AnalyzeResponse

    @Multipart @POST("analyze/review")
    suspend fun analyzeViews(@Part images: List<MultipartBody.Part>): AnalyzeResponse
}

data class RecognitionCapabilitiesDto(
    @SerializedName("review_supported") val reviewSupported: Boolean = false,
    @SerializedName("provider_mode") val providerMode: String? = null,
    @SerializedName("bbox_supported") val bboxSupported: Boolean = false,
    @SerializedName("review_image_types") val reviewImageTypes: List<String>? = null
)

data class AnalysisReviewDto(
    @SerializedName("provider_mode") val providerMode: String? = null,
    val status: String? = null,
    @SerializedName("minimum_confidence") val minimumConfidence: Double? = null,
    @SerializedName("image_count") val imageCount: Int? = null,
    @SerializedName("bbox_supported") val bboxSupported: Boolean = false
)

fun AnalyzeResponse.toPhotoAnalysis(imageUris: List<String>, fallbackMode: String? = null): PhotoAnalysis {
    val mode = when (review?.providerMode ?: fallbackMode) {
        "mock" -> RecognitionMode.MOCK
        "live" -> RecognitionMode.LIVE
        else -> RecognitionMode.UNKNOWN
    }
    val threshold = review?.minimumConfidence?.takeIf { it.isFinite() && it in 0.0..1.0 }
    val items = checkNotNull(candidates) { "Missing recognition candidates" }.mapNotNull { candidate ->
        val name = candidate.name?.trim()?.takeIf { it.isNotEmpty() } ?: return@mapNotNull null
        val score = candidate.confidence?.takeIf { it.isFinite() && it in 0.0..1.0 }
        Ingredient(name, recognition = RecognitionEvidence(name,
            candidate.rawTexts.orEmpty().filter { it.isNotBlank() }.distinct(), score,
            needsReview = threshold == null || score == null || score < threshold))
    }
    return PhotoAnalysis(items, imageUris, mode)
}
