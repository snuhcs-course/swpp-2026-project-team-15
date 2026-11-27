// AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
// Modified with Claude Code (Opus 5.5), 2026-11-27: video plays and favorites.
package com.example.mylittlechef.telemetry

import com.example.mylittlechef.data.local.UsageDataSettings
import com.example.mylittlechef.data.local.UsageDataState
import com.example.mylittlechef.data.remote.DishApi
import com.example.mylittlechef.data.remote.DishCatalogResponse
import com.example.mylittlechef.data.remote.DishDto
import com.example.mylittlechef.data.remote.DishRecipeApi
import com.example.mylittlechef.data.remote.DishSuggestRequest
import com.example.mylittlechef.data.remote.DishSuggestResponse
import com.example.mylittlechef.data.remote.DishVideosRequest
import com.example.mylittlechef.data.remote.DishVideosResponse
import com.example.mylittlechef.data.remote.RecipeViewRequest
import com.example.mylittlechef.data.remote.RecipeViewResponse
import com.example.mylittlechef.data.remote.ReviseRequest
import com.example.mylittlechef.data.remote.ReviseResponse
import com.example.mylittlechef.data.remote.TelemetryBatchDto
import com.example.mylittlechef.data.telemetry.RemoteTelemetry
import com.example.mylittlechef.domain.Telemetry
import com.example.mylittlechef.domain.Usage
import com.example.mylittlechef.domain.UsageEvent
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.viewmodel.DishRecipeSession
import com.example.mylittlechef.viewmodel.DishViewModel
import com.example.mylittlechef.viewmodel.FridgeViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestDispatcher
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response
import java.io.IOException

/** Usage data for the beta week (research/decisions/adr-007-telemetry.md). */
@OptIn(ExperimentalCoroutinesApi::class)
class TelemetryTest {
    private lateinit var dispatcher: TestDispatcher

    @Before fun setUp() { dispatcher = StandardTestDispatcher(); Dispatchers.setMain(dispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    /** Background work (the settings collector, the posts) runs only with runCurrent. */
    private fun TestScope.settle() { advanceUntilIdle(); runCurrent() }

    private class FakeSettings(state: UsageDataState) : UsageDataSettings {
        override val state = MutableStateFlow(state)
        override suspend fun installId() = "0f8fad5b-d9cb-469f-a165-70867728950e"
        override suspend fun setEnabled(enabled: Boolean) { state.value = state.value.copy(enabled = enabled) }
        override suspend fun markNoticeSeen() { state.value = state.value.copy(noticeSeen = true) }
    }

    private class Recorder : Telemetry {
        val events = mutableListOf<Usage>()
        override fun track(usage: Usage) { events += usage }
    }

    private fun http(code: Int) = HttpException(Response.error<Any>(code, "".toResponseBody("text/plain".toMediaType())))

    @Test fun nothingIsSentBeforeTheNoticeOrWhileSwitchedOff() = runTest(dispatcher) {
        val sent = mutableListOf<TelemetryBatchDto>()
        val settings = FakeSettings(UsageDataState(enabled = true, noticeSeen = false))
        val telemetry = RemoteTelemetry({ sent += it }, settings, backgroundScope, "1.0")
        settle()
        telemetry.track(Usage(UsageEvent.DISH_OPEN, dishId = "tofu-soup"))
        telemetry.flush(); settle()
        assertTrue(sent.isEmpty())

        settings.markNoticeSeen(); settings.setEnabled(false); settle()
        telemetry.track(Usage(UsageEvent.DISH_OPEN, dishId = "tofu-soup"))
        telemetry.flush(); settle()
        assertTrue(sent.isEmpty())
    }

    @Test fun batchesCarryTheInstallIdAndWireNamesAndSessionsGetNewIds() = runTest(dispatcher) {
        val sent = mutableListOf<TelemetryBatchDto>()
        val telemetry = RemoteTelemetry({ sent += it }, FakeSettings(UsageDataState(true, true)), backgroundScope, "1.0")
        settle()
        telemetry.track(Usage(UsageEvent.SESSION_START))
        telemetry.track(Usage(UsageEvent.FRIDGE_ADD, source = "photo", count = 3))
        telemetry.flush(); settle()
        telemetry.track(Usage(UsageEvent.SESSION_START))
        telemetry.flush(); settle()
        assertEquals(2, sent.size)
        assertEquals(listOf("session_start", "fridge_add"), sent[0].events.map { it.name })
        assertEquals("0f8fad5b-d9cb-469f-a165-70867728950e", sent[0].installId)
        assertEquals("photo", sent[0].events[1].source)
        assertNotEquals(sent[0].sessionId, sent[1].sessionId)
    }

    @Test fun aFullBufferIsSentAndAFailedPostIsDropped() = runTest(dispatcher) {
        var calls = 0
        val telemetry = RemoteTelemetry(
            { calls++; throw IOException("offline") }, FakeSettings(UsageDataState(true, true)), backgroundScope, "1.0", batchSize = 2
        )
        settle()
        repeat(4) { telemetry.track(Usage(UsageEvent.SCREEN_VIEW, screen = "fridge")) }
        settle()
        assertEquals(2, calls) // two full batches, no retry, no exception
    }

    @Test fun fridgeReportsSourceCountAndRecognition() = runTest(dispatcher) {
        val recorder = Recorder()
        val fridge = FridgeViewModel(telemetry = recorder)
        fridge.addIngredients(listOf(Ingredient("두부"), Ingredient("대파")), source = "photo")
        fridge.addIngredients(emptyList())
        fridge.onRecognition(found = null, durationMs = 900)
        fridge.onRecognition(found = 0, durationMs = 800)
        assertEquals(UsageEvent.FRIDGE_ADD, recorder.events[0].event)
        assertEquals(2, recorder.events[0].count)
        assertEquals(listOf("error", "empty"), recorder.events.drop(1).map { it.status })
        assertTrue(recorder.events.none { it.toString().contains("두부") }) // no ingredient names
    }

    private class FakeDishApi(val answer: suspend () -> DishSuggestResponse) : DishApi {
        override suspend fun dishes() = DishCatalogResponse(emptyList(), 0)
        override suspend fun suggest(request: DishSuggestRequest) = answer()
        override suspend fun videos(request: DishVideosRequest) = DishVideosResponse(emptyList())
    }

    private object NoRecipes : DishRecipeApi {
        override suspend fun recipe(request: RecipeViewRequest): RecipeViewResponse = throw IOException()
        override suspend fun revise(request: ReviseRequest): ReviseResponse = throw IOException()
    }

    @Test fun dishListOpeningAndPlayerErrorsAreReported() = runTest(dispatcher) {
        val recorder = Recorder()
        val ok = DishSuggestResponse("llm", listOf(DishDto("tofu-soup", "두부국", "국", listOf("두부"), emptyList(), "", emptyList(), null)))
        val vm = DishViewModel(FakeDishApi { ok }, debounceMillis = 0, recipeApi = NoRecipes, telemetry = recorder)
        vm.onFridgeChanged(listOf("두부")); settle()
        vm.selectDish("tofu-soup"); vm.selectDish("tofu-soup"); vm.onPlayerError("tofu-soup")
        assertEquals(listOf(UsageEvent.DISH_LIST, UsageEvent.DISH_OPEN, UsageEvent.PLAYER_ERROR), recorder.events.map { it.event })
        assertEquals("ok", recorder.events[0].status)
        assertEquals(1, recorder.events[0].count)

        val failing = Recorder()
        val broken = DishViewModel(FakeDishApi { throw http(502) }, debounceMillis = 0, recipeApi = NoRecipes, telemetry = failing)
        broken.onFridgeChanged(listOf("두부")); settle()
        assertEquals("error", failing.events.single().status)
        assertEquals(502, failing.events.single().code)
    }

    @Test fun videoPlaysAndFavoritesAreReportedWithTheDishId() = runTest(dispatcher) {
        val recorder = Recorder()
        val ok = DishSuggestResponse("llm", listOf(DishDto("tofu-soup", "두부국", "국", listOf("두부"), emptyList(), "", emptyList(), null)))
        val vm = DishViewModel(FakeDishApi { ok }, debounceMillis = 0, recipeApi = NoRecipes, telemetry = recorder)
        vm.onFridgeChanged(listOf("두부")); settle()
        val dish = vm.dishById("tofu-soup")!!
        vm.onVideoPlay("tofu-soup")
        vm.toggleFavorite(dish); settle()
        vm.toggleFavorite(dish); settle()
        val tail = recorder.events.drop(1)
        assertEquals(listOf(UsageEvent.VIDEO_PLAY, UsageEvent.FAVORITE_ADD, UsageEvent.FAVORITE_REMOVE), tail.map { it.event })
        assertTrue(tail.all { it.dishId == "tofu-soup" })
    }

    @Test fun aVideoCountsAsPlayedOnlyTheFirstTimeItPlays() {
        val played = java.util.concurrent.atomic.AtomicBoolean(false)
        assertEquals(false, com.example.mylittlechef.ui.dish.firstPlay(false, played))
        assertEquals(true, com.example.mylittlechef.ui.dish.firstPlay(true, played))
        assertEquals(false, com.example.mylittlechef.ui.dish.firstPlay(true, played))
    }

    @Test fun recipeAndRevisionFailuresAreReported() = runTest(dispatcher) {
        val recorder = Recorder()
        val session = DishRecipeSession(NoRecipes, this, recorder) { listOf("두부") }
        session.requestRecipe("tofu-soup"); settle()
        session.requestRevision("tofu-soup"); settle()
        assertEquals(listOf(UsageEvent.RECIPE_VIEW, UsageEvent.REVISE), recorder.events.map { it.event })
        assertEquals(listOf("error", "error"), recorder.events.map { it.status })
        assertTrue(recorder.events[1].durationMs != null)
    }
}
