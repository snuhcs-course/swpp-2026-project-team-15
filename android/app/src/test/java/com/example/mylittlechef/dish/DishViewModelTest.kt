// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.dish

import com.example.mylittlechef.data.remote.DishApi
import com.example.mylittlechef.data.remote.DishCatalogResponse
import com.example.mylittlechef.data.remote.DishDto
import com.example.mylittlechef.data.remote.DishSuggestRequest
import com.example.mylittlechef.data.remote.DishSuggestResponse
import com.example.mylittlechef.data.remote.DishVideoDto
import com.example.mylittlechef.data.remote.DishVideosRequest
import com.example.mylittlechef.data.remote.DishVideosResponse
import com.example.mylittlechef.domain.DishSort
import com.example.mylittlechef.viewmodel.DishUiState
import com.example.mylittlechef.viewmodel.DishViewModel
import com.example.mylittlechef.viewmodel.VideoUiState
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
        DishDto(id, name, "볶음밥", have, missing, "이유", emptyList(), null)

    private open class FakeApi : DishApi {
        val suggestRequests = mutableListOf<List<String>>()
        var onSuggest: suspend (DishSuggestRequest) -> DishSuggestResponse = { DishSuggestResponse("llm", emptyList()) }
        override suspend fun dishes() = DishCatalogResponse(emptyList(), 0)
        override suspend fun suggest(request: DishSuggestRequest): DishSuggestResponse {
            suggestRequests += request.ingredients
            return onSuggest(request)
        }
        val videoRequests = mutableListOf<String>()
        var onVideos: suspend (DishVideosRequest) -> DishVideosResponse = { DishVideosResponse(emptyList()) }
        override suspend fun videos(request: DishVideosRequest): DishVideosResponse {
            videoRequests += request.dishId
            return onVideos(request)
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

    @Test fun selectedDishSurvivesLikeARotation() = runTest(dispatcher) {
        val vm = DishViewModel(FakeApi())
        vm.selectDish("a")
        assertEquals("a", vm.selectedDishId)
        vm.selectDish(null)
        assertEquals(null, vm.selectedDishId)
    }

    @Test fun videosAreRequestedOncePerDishAndAFailureCanBeRetried() = runTest(dispatcher) {
        val api = FakeApi()
        api.onSuggest = { DishSuggestResponse("llm", listOf(dish("a", "김치볶음밥"))) }
        val vm = DishViewModel(api, debounceMillis = 0)
        vm.onFridgeChanged(listOf("김치"))
        advanceUntilIdle()
        val dish = (vm.state as DishUiState.Success).dishes.single()

        var fail = true
        api.onVideos = {
            if (fail) throw IOException("offline")
            DishVideosResponse(listOf(DishVideoDto("dQw4w9WgXcQ", "제목", "채널", "https://i.ytimg.com/x.jpg"), DishVideoDto("bad id", "x", "y", null)))
        }
        vm.requestVideos(dish)
        assertEquals(VideoUiState.Loading, vm.videoState("a"))
        advanceUntilIdle()
        assertTrue(vm.videoState("a") is VideoUiState.Error)

        fail = false
        vm.requestVideos(dish)
        advanceUntilIdle()
        val ok = vm.videoState("a") as VideoUiState.Success
        assertEquals(listOf("dQw4w9WgXcQ"), ok.videos.map { it.videoId }) // the id with a space is dropped
        vm.requestVideos(dish) // already loaded: no new request
        advanceUntilIdle()
        assertEquals(2, api.videoRequests.size)
    }
}
