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
    @SerializedName("search_url") val searchUrl: String?,
    @SerializedName("has_recipe") val hasRecipe: Boolean? = null,
    @SerializedName("thumbnail_url") val thumbnailUrl: String? = null
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

data class RecipeIngredientDto(val name: String?, val amount: String?, val role: String?)

data class RecipeStepDto(val n: Int?, val text: String?)

data class RecipeVideoDto(val id: String?, val title: String?, val channel: String?)

data class SourceRecipeDto(
    @SerializedName("dish_id") val dishId: String?,
    val video: RecipeVideoDto?,
    val servings: Int?,
    val ingredients: List<RecipeIngredientDto>?,
    val steps: List<RecipeStepDto>?,
    val tips: List<String>?,
    val uncertain: List<String>?,
    @SerializedName("caption_gaps") val captionGaps: Boolean?,
    val source: String? = null
)

data class RecipeViewRequest(
    @SerializedName("dish_id") val dishId: String,
    val ingredients: List<String>
)

data class RecipeViewResponse(
    @SerializedName("dish_id") val dishId: String?,
    val name: String?,
    val recipe: SourceRecipeDto?,
    val availability: List<String>?
)

data class ReviseRequest(
    @SerializedName("dish_id") val dishId: String,
    val ingredients: List<String>
)

data class RevisedIngredientDto(val name: String?, val amount: String?)

data class RevisedRecipeDto(
    val servings: Int?,
    val ingredients: List<RevisedIngredientDto>?,
    val steps: List<RecipeStepDto>?,
    val tips: List<String>?
)

data class ChangeDto(
    val reason: String?,
    @SerializedName("ingredient_refs") val ingredientRefs: List<Int>?,
    @SerializedName("step_refs") val stepRefs: List<Int>?
)

data class RevisionErrorDto(val code: String?, val message: String?)

data class ReviseResponse(
    val status: String?,
    @SerializedName("dish_id") val dishId: String?,
    val revised: RevisedRecipeDto?,
    val changes: List<ChangeDto>?,
    @SerializedName("refusal_reason") val refusalReason: String?,
    val error: RevisionErrorDto?
)

/** The recipe routes live apart from [DishApi] so the dish list code keeps its own small interface. */
interface DishRecipeApi {
    @POST("dishes/recipe")
    suspend fun recipe(@Body request: RecipeViewRequest): RecipeViewResponse

    @POST("dishes/revise")
    suspend fun revise(@Body request: ReviseRequest): ReviseResponse
}

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
    private val retrofit: Retrofit by lazy {
        val http = OkHttpClient.Builder()
            .readTimeout(90, TimeUnit.SECONDS) // a suggestion or a video search can take a while
            .retryOnConnectionFailure(false)
            .build()
        Retrofit.Builder()
            .baseUrl(BuildConfig.SERVER_BASE_URL)
            .client(http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
    }
    val api: DishApi by lazy { retrofit.create(DishApi::class.java) }
    val recipeApi: DishRecipeApi by lazy { retrofit.create(DishRecipeApi::class.java) }
}
