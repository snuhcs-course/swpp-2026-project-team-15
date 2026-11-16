// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.dish

import com.example.mylittlechef.data.remote.DishAdaptRequest
import com.example.mylittlechef.data.remote.DishAdaptResponse
import com.example.mylittlechef.data.remote.DishApi
import com.example.mylittlechef.data.remote.DishCatalogResponse
import com.example.mylittlechef.data.remote.DishDto
import com.example.mylittlechef.data.remote.DishSuggestRequest
import com.example.mylittlechef.data.remote.DishSuggestResponse
import com.example.mylittlechef.data.remote.DishVideosRequest
import com.example.mylittlechef.data.remote.DishVideosResponse
import com.example.mylittlechef.viewmodel.DishUiState
import com.example.mylittlechef.viewmodel.DishViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class DishViewModelResetTest {
    private lateinit var dispatcher: kotlinx.coroutines.test.TestDispatcher

    @Before fun setUp() { dispatcher = StandardTestDispatcher(); Dispatchers.setMain(dispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    private class Api : DishApi {
        var suggestCalls = 0
        override suspend fun dishes() = DishCatalogResponse(emptyList(), 0)
        override suspend fun suggest(request: DishSuggestRequest): DishSuggestResponse {
            suggestCalls++
            return DishSuggestResponse("llm", listOf(DishDto("a", "김치볶음밥", "볶음밥", listOf("김치"), listOf("대파"), "이유", emptyList(), null)))
        }
        override suspend fun adapt(request: DishAdaptRequest) = DishAdaptResponse(request.dishId, emptyList(), emptyList(), "", "llm")
        override suspend fun videos(request: DishVideosRequest) = DishVideosResponse(emptyList())
    }

    @Test fun resetForgetsDishesSelectionAndTheLastFridge() = runTest(dispatcher) {
        val api = Api()
        val vm = DishViewModel(api, debounceMillis = 0)
        vm.onFridgeChanged(listOf("김치"))
        advanceUntilIdle()
        vm.selectDish("a")
        assertTrue(vm.state is DishUiState.Success)

        vm.resetState()

        assertTrue(vm.state is DishUiState.EmptyFridge)
        assertNull(vm.selectedDishId)
        // The same fridge again after a reset loads again instead of being treated as unchanged.
        vm.onFridgeChanged(listOf("김치"))
        advanceUntilIdle()
        assertEquals(2, api.suggestCalls)
    }
}
