package com.example.mylittlechef.data.recipes

import com.example.mylittlechef.BuildConfig
import com.example.mylittlechef.model.Recipe
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.POST
import retrofit2.http.Path
import java.util.concurrent.TimeUnit

interface IdRecipeApi {
    @GET("recipes/catalog") suspend fun catalog(): IngredientCatalogDto
    @POST("recipes/recommendations") suspend fun recommend(
        @Body request: IdRecommendRequest,
        @Header("X-Ingredient-Catalog") version: String
    ): IdRecommendationsDto
    @GET("recipes/source/{id}") suspend fun source(@Path("id") id: Long): SourceRecipeDto
}

data class RecipeBatch(val recipes: List<Recipe>, val unmapped: List<String> = emptyList())
interface RecipeSource {
    suspend fun recommend(names: List<String>): RecipeBatch
    suspend fun original(id: Long): Recipe
}

class NetworkRecipeSource(private val api: IdRecipeApi = IntegratedApiClient.api) : RecipeSource {
    override suspend fun recommend(names: List<String>): RecipeBatch {
        val inventory = api.catalog().resolve(names)
        val result = api.recommend(IdRecommendRequest(inventory.ids), inventory.version)
        return RecipeBatch(result.mapped(inventory.ids), inventory.unmapped)
    }
    override suspend fun original(id: Long): Recipe = api.source(id).originalRecipe()
}

object IntegratedApiClient {
    val api: IdRecipeApi by lazy {
        val transport = OkHttpClient.Builder().readTimeout(210, TimeUnit.SECONDS)
            .callTimeout(240, TimeUnit.SECONDS).retryOnConnectionFailure(false).build()
        Retrofit.Builder().baseUrl(BuildConfig.SERVER_BASE_URL).client(transport)
            .addConverterFactory(GsonConverterFactory.create()).build().create(IdRecipeApi::class.java)
    }
}
