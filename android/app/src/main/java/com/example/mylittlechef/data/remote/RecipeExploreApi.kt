// AI-assisted HE exploration contract, 2026-11-10; human review pending.
package com.example.mylittlechef.data.remote

import com.google.gson.annotations.SerializedName
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST

interface RecipeExploreApi {
    @GET("recipes/explore/capabilities") suspend fun exploreCapabilities(): ExploreCapabilities
    @GET("recipes/explore/catalog") suspend fun exploreCatalog(): ExploreCatalog
    @POST("recipes/explore") suspend fun explore(@Body request: ExploreRequest): ExploreResponse
}
data class ExploreCapabilities(@SerializedName("search_supported") val searchSupported: Boolean)
data class ExploreCatalog(val items: List<ExploreCatalogItem>)
data class ExploreCatalogItem(@SerializedName("ingredient_id") val id: Int, val name: String)
data class ExploreRequest(val ingredients: List<String>, val query: String = "",
    @SerializedName("seen_ids") val seenIds: List<Long> = emptyList(), val limit: Int = 20)
data class UnregisteredIngredient(val name: String, val suggestions: List<String> = emptyList())
data class ExploreResponse(val recipes: List<RecipeDto>,
    @SerializedName("has_more") val hasMore: Boolean,
    val unregistered: List<UnregisteredIngredient> = emptyList(),
    @SerializedName("staples_assumed") val staples: List<String> = emptyList())
