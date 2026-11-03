package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.remote.AnalyzeResponse
import com.example.mylittlechef.data.remote.MyLittleChefApi
import com.example.mylittlechef.data.remote.RecipeDto
import com.example.mylittlechef.data.remote.RecommendRequest
import com.example.mylittlechef.data.remote.RecommendResponse
import com.example.mylittlechef.model.Ingredient
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import kotlinx.coroutines.withContext
import okhttp3.MultipartBody
import org.junit.Assert.assertEquals
import org.junit.Test

private class DelayedRecommendationApi : MyLittleChefApi {
    val oldResponse = CompletableDeferred<Unit>()
    val requests = mutableListOf<List<String>>()
    override suspend fun analyze(image: MultipartBody.Part): AnalyzeResponse = error("Not used")
    override suspend fun recommend(request: RecommendRequest): RecommendResponse {
        requests += request.ingredients
        val old = "두부" in request.ingredients
        if (old) withContext(NonCancellable) { oldResponse.await() }
        return RecommendResponse(
            emptyList(),
            listOf(RecipeDto(if (old) 1 else 2, if (old) "두부 요리" else "계란 요리",
                10, 1, listOf(if (old) "두부" else "계란"), emptyList(), emptyList()))
        )
    }
}

@OptIn(ExperimentalCoroutinesApi::class)
class RecipeRequestFreshnessTest {
    @Test fun lateOldResponseCannotReplaceRecipesForTheNewInventory() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        val api = DelayedRecommendationApi()
        try {
            val recipes = RecipeViewModel(api)
            recipes.refresh(listOf(Ingredient("두부"), Ingredient("계란")))
            recipes.refresh(listOf(Ingredient("계란")))
            assertEquals(listOf(2L), recipes.recommended.map { it.id })
            api.oldResponse.complete(Unit)
            advanceUntilIdle()
            assertEquals(listOf(listOf("두부", "계란"), listOf("계란")), api.requests)
            assertEquals(listOf(2L), recipes.recommended.map { it.id })
        } finally {
            api.oldResponse.complete(Unit)
            advanceUntilIdle()
            Dispatchers.resetMain()
        }
    }
}
