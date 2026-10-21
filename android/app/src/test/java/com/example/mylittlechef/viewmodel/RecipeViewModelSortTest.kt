package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.remote.AnalyzeResponse
import com.example.mylittlechef.data.remote.MyLittleChefApi
import com.example.mylittlechef.data.remote.RecipeDto
import com.example.mylittlechef.data.remote.RecommendRequest
import com.example.mylittlechef.data.remote.RecommendResponse
import com.example.mylittlechef.domain.RecipeSortType
import com.example.mylittlechef.model.Ingredient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import okhttp3.MultipartBody
import org.junit.Assert.assertEquals
import org.junit.Test

private class FakeRecipeApi : MyLittleChefApi {
    override suspend fun analyze(image: MultipartBody.Part): AnalyzeResponse = error("not used")
    override suspend fun recommend(request: RecommendRequest) = RecommendResponse(
        staplesAssumed = emptyList(),
        recipes = listOf(
            RecipeDto(1, "느린 요리", 30, 1, listOf("두부"), emptyList(), listOf("양파", "김치")),
            RecipeDto(2, "빠른 요리", 5, 1, listOf("두부"), emptyList(), emptyList()),
            RecipeDto(3, "시간 미상", null, 1, listOf("두부"), emptyList(), listOf("김치")),
            RecipeDto(4, "더 빠른 요리", 3, 1, listOf("두부"), emptyList(), listOf("김치"))
        )
    )
}

@OptIn(ExperimentalCoroutinesApi::class)
class RecipeViewModelSortTest {
    @Test fun sortingChangesVisibleOrderWithoutChangingServerOrder() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val vm = RecipeViewModel(FakeRecipeApi())
            vm.refresh(listOf(Ingredient("두부")))
            advanceUntilIdle()
            assertEquals(listOf(1L, 2L, 3L, 4L), vm.sortedRecommended(emptyList()).map { it.id })
            vm.selectSort(RecipeSortType.COOKING_TIME)
            assertEquals(listOf(4L, 2L, 1L, 3L), vm.sortedRecommended(emptyList()).map { it.id })
            vm.selectSort(RecipeSortType.FEWEST_MISSING)
            assertEquals(listOf(2L, 4L, 3L, 1L), vm.sortedRecommended(emptyList()).map { it.id })
            assertEquals(listOf(1L, 2L, 3L, 4L), vm.recommended.map { it.id })
        } finally {
            Dispatchers.resetMain()
        }
    }
}
