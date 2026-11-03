// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.model.Ingredient
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import okhttp3.MultipartBody
import org.junit.Assert.*
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class CloudRecipeRevisionTest {
    private open class Fake : MyLittleChefApi, BatchRecipeApi {
        var listCalls = 0
        val requests = mutableListOf<BatchRevisionRequest>()
        var gate: CompletableDeferred<Unit>? = null
        var failure: Throwable? = null
        val source = SourceRecipeDto(291, "원본 김치쌈밥", "20분", "2인분",
            listOf(SourceIngredientDto(223,"밥","2공기"), SourceIngredientDto(70,"김치","8장"), SourceIngredientDto(284,"소금",null)),
            listOf(SourceStepDto(1,"원본 단계")))
        var outcome = RevisionOutcomeDto("revised", RevisionResultDto("양념 제외", emptyList(),
            RevisedRecipeDto("제안 김치쌈밥","1인분",listOf(SourceIngredientDto(223,"밥","1공기")),listOf(SourceStepDto(1,"수정 단계")))),null)
        override suspend fun analyze(image: MultipartBody.Part): AnalyzeResponse = error("not used")
        override suspend fun recommend(request: RecommendRequest): RecommendResponse {
            listCalls++
            return RecommendResponse(listOf("소금"), listOf(RecipeDto(114,"두부김치",20,2,listOf("두부","김치"),listOf("원본"),listOf("깻잎"))))
        }
        override suspend fun recommendations(request: BatchRevisionRequest): BatchRecommendationsDto {
            requests.add(request)
            gate?.let { withContext(NonCancellable) { it.await() } }
            failure?.let { throw it }
            return BatchRecommendationsDto(listOf(BatchRecipeEntryDto(291,source,outcome)),listOf(284),BatchSummaryDto(1,1,1,null))
        }
    }
    private val ids = mapOf("밥" to 223, "김치" to 70, "계란" to 32, "소금" to 284)

    @Test fun normalListFailureDoesNotDisableExplicitBatchRequest() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val api=object:Fake() {
                override suspend fun recommend(request:RecommendRequest):RecommendResponse =
                    throw java.io.IOException("test list failure")
            }
            val vm=RecipeViewModel(api,ids)
            vm.refresh(listOf(Ingredient("밥"))); advanceUntilIdle()
            assertNotNull(vm.error)
            assertTrue(vm.canRequestBatchRevision)
            vm.requestBatchRevision(); advanceUntilIdle()
            assertEquals(1,api.requests.size)
            assertEquals(RevisionStatus.REVISED,vm.revisionState(291).status)
        } finally { Dispatchers.resetMain() }
    }

    @Test fun repeatRequestAfterSuccessUsesNewResponseButSuppressesConcurrentClicks() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val api=Fake(); api.gate=CompletableDeferred()
            val vm=RecipeViewModel(api,ids)
            vm.refresh(listOf(Ingredient("밥"))); advanceUntilIdle()
            vm.requestBatchRevision(); runCurrent()
            assertFalse(vm.canRequestBatchRevision)
            vm.requestBatchRevision(); assertEquals(1,api.requests.size)
            api.gate!!.complete(Unit); advanceUntilIdle()
            assertTrue(vm.canRequestBatchRevision)
            val result=api.outcome.result!!
            api.outcome=api.outcome.copy(result=result.copy(recipe=result.recipe!!.copy(name="새 AI 제안")))
            vm.requestBatchRevision(); advanceUntilIdle()
            assertEquals(2,api.requests.size)
            assertEquals("새 AI 제안",vm.revisionState(291).recipe?.name)
        } finally { Dispatchers.resetMain() }
    }

    @Test fun anotherBatchKeepsPreviousRecipeSuggestionForTheSameInventory() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val api=object:Fake() {
                override suspend fun recommendations(request:BatchRevisionRequest):BatchRecommendationsDto {
                    val response=super.recommendations(request)
                    return if(requests.size==1) response else response.copy(recipes=response.recipes.map {
                        it.copy(id=292,original=it.original.copy(id=292,name="다른 원본"))
                    })
                }
            }
            val vm=RecipeViewModel(api,ids)
            vm.refresh(listOf(Ingredient("밥"))); advanceUntilIdle()
            vm.requestBatchRevision(); advanceUntilIdle()
            vm.requestBatchRevision(); advanceUntilIdle()
            assertEquals(2,api.requests.size)
            assertEquals(RevisionStatus.REVISED,vm.revisionState(291).status)
            assertEquals(RevisionStatus.REVISED,vm.revisionState(292).status)
            assertTrue(vm.recommended.filter { it.id in listOf(291L,292L) }.all { it.revisionAvailable })
        } finally { Dispatchers.resetMain() }
    }

    @Test fun batchImageIsKeptForOriginalAndRevisedViews() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val api=object: Fake() {
                override suspend fun recommendations(request: BatchRevisionRequest): BatchRecommendationsDto {
                    val response=super.recommendations(request)
                    return response.copy(recipes=response.recipes.map { it.copy(mainImageUrl="/recipe-images/291.jpg") })
                }
            }
            val vm=RecipeViewModel(api,ids)
            vm.refresh(listOf(Ingredient("밥"))); advanceUntilIdle()
            vm.requestBatchRevision(); advanceUntilIdle()
            val url=com.example.mylittlechef.BuildConfig.SERVER_BASE_URL.trimEnd('/')+"/recipe-images/291.jpg"
            assertEquals(url,vm.find(291)!!.imageUrl)
            assertEquals(url,vm.revisionState(291).recipe!!.imageUrl)
        } finally { Dispatchers.resetMain() }
    }

    @Test fun listUsesNamesWithoutAiAndExplicitBatchKeepsDifferentRecipeIdsAndOriginals() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val api = Fake(); val vm = RecipeViewModel(api, ids)
            vm.refresh(listOf(Ingredient("밥"),Ingredient("김치")))
            advanceUntilIdle()
            assertEquals(listOf(114L),vm.recommended.map { it.id })
            assertEquals(1,api.listCalls); assertTrue(api.requests.isEmpty())
            vm.requestBatchRevision(); advanceUntilIdle()
            assertEquals(listOf(70,223),api.requests.single().ids)
            assertEquals(1,api.requests.single().revisionLimit)
            assertEquals("두부김치",vm.find(114)?.name)
            assertEquals("원본 김치쌈밥",vm.find(291)?.name)
            assertEquals("제안 김치쌈밥",vm.revisionState(291).recipe?.name)
            assertEquals(RevisionStatus.IDLE,vm.revisionState(114).status)
            vm.requestBatchRevision(); advanceUntilIdle()
            assertEquals(2,api.requests.size)
            vm.refresh(listOf(Ingredient("밥"),Ingredient("김치"))); advanceUntilIdle()
            assertTrue(vm.recommended.any { it.id == 291L })
        } finally { Dispatchers.resetMain() }
    }

    @Test fun unknownInventoryBlocksAiButNotNameBasedList() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val api = Fake(); val vm = RecipeViewModel(api, ids)
            vm.refresh(listOf(Ingredient("직접 입력 재료"))); advanceUntilIdle()
            assertTrue(vm.recommended.isNotEmpty())
            vm.requestBatchRevision(); advanceUntilIdle()
            assertTrue(api.requests.isEmpty())
            assertTrue(vm.batchRevisionMessage!!.contains("직접 입력 재료"))
        } finally { Dispatchers.resetMain() }
    }

    @Test fun contextChangeDiscardsLateBatchResponseAndInvalidatesSeenAvailability() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val api=Fake(); api.gate=CompletableDeferred()
            val vm=RecipeViewModel(api,ids)
            vm.refresh(listOf(Ingredient("밥"))); advanceUntilIdle()
            vm.requestBatchRevision(); runCurrent()
            vm.updateUserContext(listOf(Ingredient("김치")),listOf("우유"),emptyList())
            api.gate!!.complete(Unit); advanceUntilIdle()
            assertEquals(RevisionStatus.IDLE,vm.revisionState(291).status)
            assertNull(vm.find(291)); assertFalse(vm.find(114)!!.availabilityKnown)
            assertFalse(vm.batchRevisionLoading)
        } finally { Dispatchers.resetMain() }
    }

    @Test fun refusalAndFailureAreNotShownAsRevisedAndFailureCanRetry() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val api=Fake(); val vm=RecipeViewModel(api,ids)
            vm.refresh(listOf(Ingredient("밥"))); advanceUntilIdle()
            api.outcome=RevisionOutcomeDto("failed",null,RevisionErrorDto("quota_exceeded"))
            vm.requestBatchRevision(); advanceUntilIdle()
            assertEquals(RevisionStatus.ERROR,vm.revisionState(291).status)
            assertTrue(vm.batchRevisionMessage!!.contains("한도"))
            api.outcome=RevisionOutcomeDto("refused",RevisionResultDto("재료 부족",emptyList(),null),null)
            vm.requestBatchRevision(); advanceUntilIdle()
            assertEquals(RevisionStatus.REFUSED,vm.revisionState(291).status)
            assertNull(vm.revisionState(291).recipe)
            assertFalse(vm.find(291)!!.revisionCandidate)
            vm.requestBatchRevision(); advanceUntilIdle()
            assertEquals(3,api.requests.size)
        } finally { Dispatchers.resetMain() }
    }

    @Test fun serverReturnedIdNameMismatchIsRejectedInsteadOfReassociatingDish() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val api=object: Fake() {
                override suspend fun recommendations(request: BatchRevisionRequest) =
                    super.recommendations(request).copy(recipes=listOf(BatchRecipeEntryDto(999,source,outcome)))
            }
            val vm=RecipeViewModel(api,ids)
            vm.refresh(listOf(Ingredient("밥"))); advanceUntilIdle()
            vm.requestBatchRevision(); advanceUntilIdle()
            assertEquals(RevisionStatus.IDLE,vm.revisionState(999).status)
            assertNotNull(vm.batchRevisionMessage)
        } finally { Dispatchers.resetMain() }
    }

    @Test fun batchOriginalAddsQuantitiesWithoutLosingAuthoritativeListAvailability() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val api=object: Fake() {
                override suspend fun recommend(request:RecommendRequest)=RecommendResponse(emptyList(),
                    listOf(RecipeDto(291,"원본 김치쌈밥",20,2,listOf("밥","김치"),listOf("원본 단계"),listOf("소금"))))
            }
            val vm=RecipeViewModel(api,ids)
            vm.refresh(listOf(Ingredient("밥"))); advanceUntilIdle()
            vm.requestBatchRevision(); advanceUntilIdle()
            assertEquals(listOf("2공기","8장",null),vm.find(291)!!.ingredientQuantities)
            assertTrue(vm.find(291)!!.availabilityKnown)
            assertEquals(listOf(Ingredient("소금")),vm.find(291)!!.missing)
            assertTrue(vm.find(291)!!.revisionAvailable)
        } finally { Dispatchers.resetMain() }
    }
}
