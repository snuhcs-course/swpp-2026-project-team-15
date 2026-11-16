// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data.remote

import com.example.mylittlechef.BuildConfig
import com.google.gson.annotations.SerializedName
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import java.util.concurrent.TimeUnit

// Field names mirror the server's /dishes routes; Gson turns a mismatch into null, so lists are read with orEmpty().

data class DishCatalogResponse(val dishes: List<DishSummaryDto>?, val count: Int?)

data class DishSummaryDto(
    val id: String?,
    val name: String?,
    val category: String?,
    @SerializedName("key_ingredients") val keyIngredients: List<String>?,
    val aliases: List<String>?
)

data class DishSuggestRequest(val ingredients: List<String>)

data class DishSuggestResponse(val source: String?, val dishes: List<DishDto>?)

data class DishDto(
    val id: String?,
    val name: String?,
    val category: String?,
    val have: List<String>?,
    val missing: List<String>?,
    val reason: String?,
    val keywords: List<String>?,
    @SerializedName("search_url") val searchUrl: String?
)

data class DishVideoDto(
    @SerializedName("video_id") val videoId: String?,
    val title: String?,
    val channel: String?,
    @SerializedName("thumbnail_url") val thumbnailUrl: String?
)

data class DishVideosRequest(@SerializedName("dish_id") val dishId: String)

data class DishVideosResponse(val videos: List<DishVideoDto>?)

data class DishAdaptRequest(
    @SerializedName("dish_id") val dishId: String,
    val ingredients: List<String>,
    val missing: List<String> = emptyList()
)

data class DishAdaptResponse(
    @SerializedName("dish_id") val dishId: String?,
    val substitutions: List<DishSubstitutionDto>?,
    @SerializedName("skip_ok") val skipOk: List<String>?,
    val note: String?,
    val source: String?
)

data class DishSubstitutionDto(val missing: String?, val suggestion: String?, val uses: List<String>?)

interface DishApi {
    @GET("dishes")
    suspend fun dishes(): DishCatalogResponse

    @POST("dishes/suggest")
    suspend fun suggest(@Body request: DishSuggestRequest): DishSuggestResponse

    @POST("dishes/videos")
    suspend fun videos(@Body request: DishVideosRequest): DishVideosResponse

    @POST("dishes/adapt")
    suspend fun adapt(@Body request: DishAdaptRequest): DishAdaptResponse
}

/** Own Retrofit instance so the existing ApiClient and its interfaces stay unchanged. */
object DishApiClient {
    val api: DishApi by lazy {
        val http = OkHttpClient.Builder()
            .readTimeout(90, TimeUnit.SECONDS) // a suggestion or a video search can take a while
            .retryOnConnectionFailure(false)
            .build()
        Retrofit.Builder()
            .baseUrl(BuildConfig.SERVER_BASE_URL)
            .client(http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(DishApi::class.java)
    }
}
