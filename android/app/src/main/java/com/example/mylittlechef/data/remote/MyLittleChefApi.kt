// Restored and integrated with Codex, 2026-10-29; human review pending.
// AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
// Ingredient catalog API added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
package com.example.mylittlechef.data.remote

import com.example.mylittlechef.BuildConfig
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import java.util.concurrent.TimeUnit

interface MyLittleChefApi {
    @Multipart
    @POST("analyze")
    suspend fun analyze(@Part image: MultipartBody.Part): AnalyzeResponse

    @POST("recipes/recommend")
    suspend fun recommend(@Body request: RecommendRequest): RecommendResponse

}

/** Several views of the same fridge in one request. Kept apart so existing API fakes stay valid. */
interface MultiImageApi {
    @Multipart
    @POST("analyze")
    suspend fun analyzeViews(@Part images: List<MultipartBody.Part>): AnalyzeResponse
}

interface IngredientSupportApi : MyLittleChefApi {
    @GET("recipes/ingredients")
    suspend fun ingredientNames(): IngredientCatalogResponse

    // Ingredient suggestions added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
    @POST("recipes/ingredient-suggestions")
    suspend fun ingredientSuggestions(
        @Body request: IngredientSuggestionRequest
    ): IngredientSuggestionResponse
}

object ApiClient {
    // The phone reaches the laptop's server through `adb reverse tcp:8000 tcp:8000`.
    private const val BASE_URL = BuildConfig.SERVER_BASE_URL

    private val retrofit: Retrofit by lazy {
        val http = OkHttpClient.Builder()
            // Image recognition can exceed OkHttp's 10 s default read timeout.
            .readTimeout(60, TimeUnit.SECONDS)
            .build()
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }

    val api: IngredientSupportApi by lazy { retrofit.create(IngredientSupportApi::class.java) }

    val multiImageApi: MultiImageApi by lazy { retrofit.create(MultiImageApi::class.java) }
}
