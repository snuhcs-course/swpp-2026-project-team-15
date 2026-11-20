// AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.dish

import com.example.mylittlechef.data.local.FavoriteDish
import com.example.mylittlechef.data.local.InMemoryFavoriteDishes
import com.example.mylittlechef.data.local.PreferencesFavoriteDishes
import com.example.mylittlechef.data.remote.DishApi
import com.example.mylittlechef.data.remote.DishCatalogResponse
import com.example.mylittlechef.data.remote.DishDto
import com.example.mylittlechef.data.remote.DishSuggestRequest
import com.example.mylittlechef.data.remote.DishSuggestResponse
import com.example.mylittlechef.data.remote.DishVideosRequest
import com.example.mylittlechef.data.remote.DishVideosResponse
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

/** The #24 recipe list on the YouTube-based dishes: bookmarks, hide for this list, search within it. */
@OptIn(ExperimentalCoroutinesApi::class)
class DishListActionsTest {
    private val dispatcher = StandardTestDispatcher()
    @Before fun setUp() = Dispatchers.setMain(dispatcher)
    @After fun tearDown() = Dispatchers.resetMain()

    private class Api : DishApi {
        override suspend fun dishes() = DishCatalogResponse(emptyList(), 0)
        override suspend fun suggest(request: DishSuggestRequest) = DishSuggestResponse("llm", listOf(
            DishDto("kimchi-fried-rice", "김치볶음밥", "볶음밥", listOf("김치"), emptyList(), "", emptyList(), null),
            DishDto("egg-roll", "계란말이", "계란", listOf("계란"), listOf("대파"), "", emptyList(), null)
        ))
        override suspend fun videos(request: DishVideosRequest) = DishVideosResponse(emptyList())
    }

    @Test fun searchFiltersOnlyTheSuggestedListAndHideCanBeUndone() = runTest(dispatcher) {
        val vm = DishViewModel(Api(), debounceMillis = 0)
        vm.onFridgeChanged(listOf("김치", "계란"))
        advanceUntilIdle()
        assertEquals(listOf("계란말이"), vm.visibleSuggestions("계란").map { it.name })
        vm.hide("egg-roll")
        assertEquals(listOf("김치볶음밥"), vm.visibleSuggestions("").map { it.name })
        vm.undoHide()
        assertEquals(2, vm.visibleSuggestions("").size)
        assertNull(vm.lastHidden)
        vm.hide("egg-roll")
        vm.onFridgeChanged(listOf("김치", "계란", "밥")) // a new list shows hidden dishes again
        advanceUntilIdle()
        assertEquals(2, vm.visibleSuggestions("").size)
    }

    @Test fun bookmarksOutliveTheSuggestionListAndOpenAsDishes() = runTest(dispatcher) {
        val store = InMemoryFavoriteDishes()
        val vm = DishViewModel(Api(), debounceMillis = 0, favoriteStore = store)
        vm.onFridgeChanged(listOf("김치"))
        advanceUntilIdle()
        vm.toggleFavorite(vm.visibleSuggestions("").first { it.id == "egg-roll" })
        advanceUntilIdle()
        assertTrue(vm.isFavorite("egg-roll"))
        vm.onFridgeChanged(emptyList())
        advanceUntilIdle()
        val saved = vm.favoriteDishes().single()
        assertEquals("계란말이", saved.name)
        assertEquals("계란말이", vm.dishById("egg-roll")?.name)
        assertTrue(!vm.isSuggested("egg-roll"))
    }

    @Test fun storedBookmarkRoundTripsAndRejectsBrokenEntries() {
        val dish = FavoriteDish("a-b", "이름 · 있음", null)
        assertEquals(dish, PreferencesFavoriteDishes.decode(PreferencesFavoriteDishes.encode(dish)))
        assertNull(PreferencesFavoriteDishes.decode("only-one-part"))
    }
}
