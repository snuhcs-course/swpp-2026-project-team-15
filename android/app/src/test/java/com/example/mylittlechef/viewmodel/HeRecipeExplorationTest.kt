// AI-assisted HE regressions, 2026-11-10; human review pending.
package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.model.Ingredient
import okhttp3.MultipartBody
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response
import okhttp3.ResponseBody.Companion.toResponseBody

@OptIn(ExperimentalCoroutinesApi::class)
class HeRecipeExplorationTest {
    @Test fun olderServerFallsBackOnceAndKeepsHiddenRecipesOnUnchangedReturn() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            var legacyCalls=0
            val source=object: Fake() {
                override suspend fun exploreCapabilities(): ExploreCapabilities =
                    throw HttpException(Response.error<Any>(404,"Unsupported".toResponseBody()))
            }
            val api=object: RecipeExploreApi by source, MyLittleChefApi {
                override suspend fun analyze(image: MultipartBody.Part): AnalyzeResponse = error("No calls")
                override suspend fun recommend(request: RecommendRequest): RecommendResponse {
                    legacyCalls++
                    return RecommendResponse(emptyList(),listOf(RecipeDto(1,"두부 요리",10,1,listOf("두부"),emptyList(),emptyList())))
                }
            }
            val vm=RecipeViewModel(api); val fridge=listOf(Ingredient("두부"))
            vm.refresh(fridge); advanceUntilIdle()
            assertFalse(vm.fullSearchSupported)
            assertEquals(listOf(1L),vm.recommended.map { it.id })
            vm.hideRecipe(1)
            vm.refresh(fridge); advanceUntilIdle()
            assertEquals(1,legacyCalls)
            assertTrue(vm.sortedRecommended(fridge).isEmpty())
            vm.undoHideRecipe()
            assertEquals(listOf(1L),vm.sortedRecommended(fridge).map { it.id })
        } finally { Dispatchers.resetMain() }
    }
    @Test fun recipeFacadeUsesSupportedExplorationRatherThanLegacyTopTwenty() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val source = Fake()
            val api=object : RecipeExploreApi by source, MyLittleChefApi {
                override suspend fun analyze(image: MultipartBody.Part): AnalyzeResponse = error("No photos")
                override suspend fun recommend(request: RecommendRequest) = RecommendResponse(emptyList(), emptyList())
            }
            val vm=RecipeViewModel(api)
            vm.refresh(listOf(Ingredient("두부"))); advanceUntilIdle()
            assertEquals(listOf(1L), vm.recommended.map { it.id })
            assertEquals(1, source.requests.size)
        } finally { Dispatchers.resetMain() }
    }
    private open class Fake : RecipeExploreApi {
        val requests = mutableListOf<ExploreRequest>()
        var gate: CompletableDeferred<Unit>? = null
        override suspend fun exploreCapabilities() = ExploreCapabilities(true)
        override suspend fun exploreCatalog() = ExploreCatalog(emptyList())
        override suspend fun explore(request: ExploreRequest): ExploreResponse {
            requests.add(request)
            gate?.let { withContext(NonCancellable) { it.await() } }
            val id = if(request.seenIds.isEmpty()) 1L else 2L
            return ExploreResponse(listOf(RecipeDto(id,"두부 요리 $id",10,1,listOf("두부"),listOf("조리"),emptyList())), id == 1L)
        }
    }
    @Test fun capabilityTimeoutHasVisibleRecoveryInsteadOfSilentEmptySuccess() = runTest {
        val api=object: Fake() { override suspend fun exploreCapabilities(): ExploreCapabilities {
            delay(4_000); return ExploreCapabilities(true)
        } }
        val state=RecipeExploration(api,this) {}
        state.load(listOf("두부")); advanceUntilIdle()
        assertFalse(state.loading)
        assertNotNull(state.error)
        assertTrue(api.requests.isEmpty())
    }
    @Test fun unchangedReturnToTheScreenPreservesPageHiddenStateAndUndo() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val source=Fake()
            val api=object: RecipeExploreApi by source, MyLittleChefApi {
                override suspend fun analyze(image: MultipartBody.Part): AnalyzeResponse = error("No calls")
                override suspend fun recommend(request: RecommendRequest) = RecommendResponse(emptyList(),emptyList())
            }
            val vm=RecipeViewModel(api); val fridge=listOf(Ingredient("두부"))
            vm.refresh(fridge); advanceUntilIdle()
            vm.otherRecommendations(fridge); advanceUntilIdle()
            vm.hideRecipe(2)
            vm.refresh(fridge); advanceUntilIdle()
            assertEquals(2,source.requests.size)
            assertTrue(vm.sortedRecommended(fridge).isEmpty())
            vm.undoHideRecipe()
            assertEquals(listOf(2L),vm.sortedRecommended(fridge).map { it.id })
        } finally { Dispatchers.resetMain() }
    }
    @Test fun cachedAiBadgesAndOutOfPageSuggestionsSurviveAnotherExploration() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val source=Fake()
            val api=object: RecipeExploreApi by source, MyLittleChefApi, BatchRecipeApi {
                override suspend fun analyze(image: MultipartBody.Part): AnalyzeResponse = error("No calls")
                override suspend fun recommend(request: RecommendRequest) = RecommendResponse(emptyList(),emptyList())
                override suspend fun recommendations(request: BatchRevisionRequest): BatchRecommendationsDto {
                    val entries=listOf(1L,99L).map { id ->
                        val original=SourceRecipeDto(id,"두부 요리 $id","10분","1인분",
                            listOf(SourceIngredientDto(1,"두부",null)),listOf(SourceStepDto(1,"원본")))
                        val outcome=RevisionOutcomeDto("revised",RevisionResultDto("양 조절",emptyList(),
                            RevisedRecipeDto(original.name,"1인분",original.ingredients,original.steps)),null)
                        BatchRecipeEntryDto(id,original,outcome)
                    }
                    return BatchRecommendationsDto(entries,emptyList(),BatchSummaryDto(1,2,2,null))
                }
            }
            val vm=RecipeViewModel(api,mapOf("두부" to 1)); val fridge=listOf(Ingredient("두부"))
            vm.refresh(fridge); advanceUntilIdle()
            vm.requestBatchRevision(); advanceUntilIdle()
            assertTrue(vm.recommended.first { it.id == 1L }.revisionAvailable)
            vm.search("두부",fridge); advanceUntilIdle()
            assertTrue(vm.recommended.first { it.id == 1L }.revisionAvailable)
            assertTrue(vm.recommended.any { it.id == 99L })
        } finally { Dispatchers.resetMain() }
    }
    @Test fun nextPagePassesSeenIdsAndSearchResetsExploration() = runTest {
        val api=Fake(); var ids=emptyList<Long>()
        val state=RecipeExploration(api,this) { ids=it.map { row -> row.id } }
        state.load(listOf("두부")); advanceUntilIdle()
        assertEquals(listOf(1L),ids)
        state.load(listOf("두부"), next=true); advanceUntilIdle()
        assertEquals(listOf(1L),api.requests.last().seenIds)
        assertEquals(listOf(2L),ids); assertFalse(state.hasMore)
        state.load(listOf("두부"),"국"); advanceUntilIdle()
        assertTrue(api.requests.last().seenIds.isEmpty())
        assertEquals("국",api.requests.last().query)
    }
    @Test fun hideAndUndoAreSessionOnlyAndInventoryChangeInvalidatesLateResponses() = runTest {
        val api=Fake(); var ids=emptyList<Long>()
        val state=RecipeExploration(api,this) { ids=it.map { row -> row.id } }
        state.load(listOf("두부")); advanceUntilIdle()
        state.hide(1); assertEquals(setOf(1L),state.hidden)
        state.undoHide(); assertTrue(state.hidden.isEmpty())
        api.gate=CompletableDeferred()
        state.load(listOf("두부"),next=true); runCurrent()
        state.invalidate(); api.gate!!.complete(Unit); advanceUntilIdle()
        assertEquals(listOf(1L),ids)
        assertFalse(state.loading)
    }
}
