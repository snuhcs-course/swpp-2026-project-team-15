// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.dish

import com.example.mylittlechef.data.remote.DishAdaptRequest
import com.example.mylittlechef.data.remote.DishAdaptResponse
import com.example.mylittlechef.data.remote.DishApi
import com.example.mylittlechef.data.remote.DishCatalogResponse
import com.example.mylittlechef.data.remote.DishDto
import com.example.mylittlechef.data.remote.DishSubstitutionDto
import com.example.mylittlechef.data.remote.DishSuggestRequest
import com.example.mylittlechef.data.remote.DishSuggestResponse
import com.example.mylittlechef.domain.DishSort
import com.example.mylittlechef.viewmodel.AdaptUiState
import com.example.mylittlechef.viewmodel.DishUiState
import com.example.mylittlechef.viewmodel.DishViewModel
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class DishViewModelTest {
    private lateinit var dispatcher: kotlinx.coroutines.test.TestDispatcher

    @Before fun setUp() { dispatcher = StandardTestDispatcher(); Dispatchers.setMain(dispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    private fun dish(id: String, name: String, have: List<String> = listOf("김치"), missing: List<String> = emptyList()) =
        DishDto(id, name, "볶음밥", have, missing, "이유", emptyList(), emptyList(), null)

    private open class FakeApi : DishApi {
        val suggestRequests = mutableListOf<List<String>>()
        val adaptRequests = mutableListOf<DishAdaptRequest>()
        var onSuggest: suspend (DishSuggestRequest) -> DishSuggestResponse = { DishSuggestResponse("llm", emptyList()) }
        var onAdapt: suspend (DishAdaptRequest) -> DishAdaptResponse = { DishAdaptResponse(it.dishId, emptyList(), emptyList(), "", "llm") }
        override suspend fun dishes() = DishCatalogResponse(emptyList(), 0)
        override suspend fun suggest(request: DishSuggestRequest): DishSuggestResponse {
            suggestRequests += request.ingredients
            return onSuggest(request)
        }
        override suspend fun adapt(request: DishAdaptRequest): DishAdaptResponse {
            adaptRequests += request
            return onAdapt(request)
        }
    }

    @Test fun successShowsDishesSortedByFewestMissing() = runTest(dispatcher) {
        val api = FakeApi().apply {
            onSuggest = {
                DishSuggestResponse("llm", listOf(
                    dish("a", "가", missing = listOf("x", "y")),
                    dish("b", "나", missing = emptyList())
                ))
            }
        }
        val vm = DishViewModel(api, debounceMillis = 400)
        vm.onFridgeChanged(listOf("김치", "쌀"))
        assertTrue(vm.state is DishUiState.Loading)
        advanceUntilIdle()
        val s = vm.state as DishUiState.Success
        assertEquals(listOf("b", "a"), s.dishes.map { it.id })
        assertEquals("llm", s.source)
        vm.selectSort(DishSort.NAME)
        assertEquals(listOf("a", "b"), (vm.state as DishUiState.Success).dishes.map { it.id })
    }

    @Test fun emptyFridgeNeverCallsTheServer() = runTest(dispatcher) {
        val api = FakeApi()
        val vm = DishViewModel(api)
        vm.onFridgeChanged(emptyList())
        advanceUntilIdle()
        assertTrue(vm.state is DishUiState.EmptyFridge)
        assertTrue(api.suggestRequests.isEmpty())
    }

    @Test fun noDishesFoundIsItsOwnState() = runTest(dispatcher) {
        val vm = DishViewModel(FakeApi())
        vm.onFridgeChanged(listOf("김치"))
        advanceUntilIdle()
        assertTrue(vm.state is DishUiState.NoMatch)
    }

    @Test fun errorShowsAMessageAndRetrySucceeds() = runTest(dispatcher) {
        var fail = true
        val api = FakeApi().apply {
            onSuggest = {
                if (fail) throw IOException("offline")
                DishSuggestResponse("rules", listOf(dish("a", "가")))
            }
        }
        val vm = DishViewModel(api)
        vm.onFridgeChanged(listOf("김치"))
        advanceUntilIdle()
        assertTrue((vm.state as DishUiState.Error).message.contains("서버에 연결하지 못했어요"))
        fail = false
        vm.retry()
        advanceUntilIdle()
        assertEquals("rules", (vm.state as DishUiState.Success).source)
        assertEquals(2, api.suggestRequests.size)
    }

    @Test fun serverWithoutTheRouteGetsAClearMessage() = runTest(dispatcher) {
        val body = "".toResponseBody("application/json".toMediaType())
        val api = FakeApi().apply { onSuggest = { throw HttpException(Response.error<Any>(404, body)) } }
        val vm = DishViewModel(api)
        vm.onFridgeChanged(listOf("김치"))
        advanceUntilIdle()
        assertTrue((vm.state as DishUiState.Error).message.contains("지원하지 않아요"))
    }

    @Test fun sameFridgeAgainDoesNotRequestAgain() = runTest(dispatcher) {
        val api = FakeApi().apply { onSuggest = { DishSuggestResponse("llm", listOf(dish("a", "가"))) } }
        val vm = DishViewModel(api)
        vm.onFridgeChanged(listOf("김치", "쌀"))
        advanceUntilIdle()
        vm.onFridgeChanged(listOf("김치", "쌀")) // tab switch or rotation
        vm.onFridgeChanged(listOf(" 김치 ", "쌀", "쌀"))
        advanceUntilIdle()
        assertEquals(1, api.suggestRequests.size)
        assertTrue(vm.state is DishUiState.Success)
    }

    @Test fun fridgeChangesAreDebouncedAndOnlyTheLastOneIsRequested() = runTest(dispatcher) {
        val api = FakeApi().apply { onSuggest = { DishSuggestResponse("llm", listOf(dish("a", "가"))) } }
        val vm = DishViewModel(api, debounceMillis = 400)
        vm.onFridgeChanged(listOf("김치"))
        advanceTimeBy(100)
        vm.onFridgeChanged(listOf("김치", "쌀"))
        advanceTimeBy(100)
        vm.onFridgeChanged(listOf("김치", "쌀", "돼지고기"))
        advanceUntilIdle()
        assertEquals(listOf(listOf("김치", "쌀", "돼지고기")), api.suggestRequests)
    }

    @Test fun lateAnswerForAnOldFridgeCannotReplaceTheNewOne() = runTest(dispatcher) {
        val gate = CompletableDeferred<Unit>()
        val api = FakeApi().apply {
            onSuggest = { request ->
                if (request.ingredients == listOf("김치")) gate.await()
                DishSuggestResponse("llm", listOf(dish(request.ingredients.joinToString(), request.ingredients.joinToString())))
            }
        }
        val vm = DishViewModel(api, debounceMillis = 0)
        vm.onFridgeChanged(listOf("김치"))
        advanceUntilIdle()
        vm.onFridgeChanged(listOf("쌀"))
        advanceUntilIdle()
        gate.complete(Unit)
        advanceUntilIdle()
        assertEquals("쌀", (vm.state as DishUiState.Success).dishes.single().name)
    }

    @Test fun adaptShowsLoadingThenResultAndIsClearedWhenTheFridgeChanges() = runTest(dispatcher) {
        val gate = CompletableDeferred<Unit>()
        val api = FakeApi().apply {
            onSuggest = { DishSuggestResponse("llm", listOf(dish("a", "가", missing = listOf("대파")))) }
            onAdapt = {
                gate.await()
                DishAdaptResponse(it.dishId, listOf(DishSubstitutionDto("대파", "양파로 대체", listOf("양파"))), listOf("깨"), "참고", "llm")
            }
        }
        val vm = DishViewModel(api, debounceMillis = 0)
        vm.onFridgeChanged(listOf("김치", "양파"))
        advanceUntilIdle()
        val dish = (vm.state as DishUiState.Success).dishes.single()
        vm.requestAdapt(dish)
        vm.requestAdapt(dish) // second tap while loading is ignored
        advanceUntilIdle()
        assertTrue(vm.adaptState("a") is AdaptUiState.Loading)
        gate.complete(Unit)
        advanceUntilIdle()
        val result = (vm.adaptState("a") as AdaptUiState.Success).adaptation
        assertEquals("양파로 대체", result.substitutions.single().suggestion)
        assertEquals(1, api.adaptRequests.size)
        assertEquals(listOf("김치", "양파"), api.adaptRequests.single().ingredients)
        vm.onFridgeChanged(listOf("김치"))
        advanceUntilIdle()
        assertEquals(null, vm.adaptState("a"))
    }

    @Test fun adaptFailureCanBeRetried() = runTest(dispatcher) {
        var fail = true
        val api = FakeApi().apply {
            onSuggest = { DishSuggestResponse("llm", listOf(dish("a", "가", missing = listOf("대파")))) }
            onAdapt = { if (fail) throw IOException("x") else DishAdaptResponse(it.dishId, emptyList(), listOf("대파"), "", "llm") }
        }
        val vm = DishViewModel(api, debounceMillis = 0)
        vm.onFridgeChanged(listOf("김치"))
        advanceUntilIdle()
        val dish = (vm.state as DishUiState.Success).dishes.single()
        vm.requestAdapt(dish)
        advanceUntilIdle()
        assertTrue(vm.adaptState("a") is AdaptUiState.Error)
        fail = false
        vm.requestAdapt(dish)
        advanceUntilIdle()
        assertEquals(listOf("대파"), (vm.adaptState("a") as AdaptUiState.Success).adaptation.skipOk)
    }

    @Test fun selectedDishSurvivesLikeARotation() = runTest(dispatcher) {
        val vm = DishViewModel(FakeApi())
        vm.selectDish("a")
        assertEquals("a", vm.selectedDishId)
        vm.selectDish(null)
        assertEquals(null, vm.selectedDishId)
    }
}
