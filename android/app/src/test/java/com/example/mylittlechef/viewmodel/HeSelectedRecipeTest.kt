// AI-assisted selected-recipe regressions, 2026-11-10; human review pending. No paid calls.
package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.model.*
import com.google.gson.Gson
import com.google.gson.JsonNull
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import okhttp3.ResponseBody.Companion.toResponseBody
import okhttp3.MultipartBody
import org.junit.Assert.*
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response

@OptIn(ExperimentalCoroutinesApi::class)
class HeSelectedRecipeTest {
    private val original=Recipe(7,"계란 요리",10,2,listOf(Ingredient("계란")),listOf("원본 단계"))
    private open class Fake: SelectedRecipeApi {
        val calls=mutableListOf<Pair<Long,SelectedRevisionRequest>>()
        var supported=true
        var failure: Throwable?=null
        var gate: CompletableDeferred<Unit>?=null
        override suspend fun selectedCapabilities()=SelectedCapabilities(supported,"mock")
        override suspend fun reviseSelected(id:Long,request:SelectedRevisionRequest):SelectedRevisionResponse {
            calls.add(id to request)
            gate?.let { withContext(NonCancellable) { it.await() } }
            failure?.let { throw it }
            val source=SourceRecipeDto(id,"계란 요리","10분","2인분",
                listOf(SourceIngredientDto(1,"계란","2개")),listOf(SourceStepDto(1,"원본 단계")))
            return SelectedRevisionResponse(id,source,emptyList(),RevisionOutcomeDto("revised",
                RevisionResultDto("1인분으로 조절",listOf(RevisionChangeDto("quantity","계란 양 조절")),
                    RevisedRecipeDto("AI 계란 요리","1인분",listOf(SourceIngredientDto(1,"계란","1개")),listOf(SourceStepDto(1,"수정 단계")))),null),"mock")
        }
    }
    @Test fun facadeConnectsSelectedRequestsAndRetainsBadgesOnAnotherListLoad()=runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val selected=Fake()
            val api=object: SelectedRecipeApi by selected, MyLittleChefApi {
                override suspend fun analyze(image:MultipartBody.Part):AnalyzeResponse=error("No calls")
                override suspend fun recommend(request:RecommendRequest)=RecommendResponse(emptyList(),
                    listOf(RecipeDto(7,"계란 요리",10,2,listOf("계란"),listOf("원본 단계"),emptyList())))
            }
            val vm=RecipeViewModel(api)
            val fridge=listOf(Ingredient("계란"))
            vm.refresh(fridge); advanceUntilIdle(); vm.requestRevision(7); advanceUntilIdle()
            assertEquals(1,selected.calls.size)
            assertEquals(RevisionStatus.REVISED,vm.revisionState(7).status)
            assertEquals(listOf(7L),vm.cachedAiRecipes(fridge).map { it.id })
            vm.search("계란",fridge); advanceUntilIdle()
            assertTrue(vm.recommended.single().revisionAvailable)
        } finally { Dispatchers.resetMain() }
    }
    @Test fun sendsOnlyChosenIdPreservesOriginalAndReusesSameContextResult()=runTest {
        val api=Fake(); val originals=mutableListOf<Recipe>()
        val session=SelectedRecipeSession(api,this,originals::add)
        session.updateContext(RecipeContext(listOf("계란")))
        session.request(original); advanceUntilIdle()
        assertEquals(7L,api.calls.single().first)
        assertEquals(listOf("계란"),api.calls.single().second.ingredients)
        assertEquals(RevisionStatus.REVISED,session.state(7).status)
        assertEquals(listOf("원본 단계"),session.state(7).original!!.steps)
        assertEquals(listOf("수정 단계"),session.state(7).suggestion!!.steps)
        session.request(original); advanceUntilIdle(); assertEquals(1,api.calls.size)
        assertEquals(1,originals.size)
    }
    @Test fun cancellationAndRetryCannotBeOverwrittenByTheFirstLateResponse()=runTest {
        val api=Fake(); val gate=CompletableDeferred<Unit>(); api.gate=gate
        val session=SelectedRecipeSession(api,this)
        session.updateContext(RecipeContext(listOf("계란")))
        session.request(original); runCurrent()
        session.cancel(7); assertEquals(SelectedProblem.CANCELLED,session.state(7).problem)
        api.gate=null; session.request(original); runCurrent()
        assertEquals(RevisionStatus.REVISED,session.state(7).status)
        gate.complete(Unit); advanceUntilIdle()
        assertEquals(RevisionStatus.REVISED,session.state(7).status)
        assertEquals(2,api.calls.size)
    }
    @Test fun inventoryChangeDropsLateResultAndDoesNotAutomaticallyCallAgain()=runTest {
        val api=Fake(); api.gate=CompletableDeferred()
        val session=SelectedRecipeSession(api,this)
        session.updateContext(RecipeContext(listOf("계란")))
        session.request(original); runCurrent()
        session.updateContext(RecipeContext(listOf("두부")))
        api.gate!!.complete(Unit); advanceUntilIdle()
        assertEquals(RevisionStatus.IDLE,session.state(7).status)
        assertTrue(session.cachedOriginals.isEmpty()); assertEquals(1,api.calls.size)
    }
    @Test fun unsupportedServerMakesNoRevisionCall()=runTest {
        val api=Fake(); api.supported=false
        val session=SelectedRecipeSession(api,this)
        session.updateContext(RecipeContext(listOf("계란"))); session.request(original); advanceUntilIdle()
        assertEquals(SelectedProblem.UNSUPPORTED,session.state(7).problem)
        assertTrue(api.calls.isEmpty())
    }
    @Test fun rateLimitAndUnknownIngredientsExposeRecoveryAndRequireOptIn()=runTest {
        val api=Fake(); val session=SelectedRecipeSession(api,this)
        session.updateContext(RecipeContext(listOf("계란","미등록")))
        api.failure=HttpException(Response.error<Any>(429,"Limit".toResponseBody()))
        session.request(original); advanceUntilIdle()
        assertEquals(SelectedProblem.RATE_LIMIT,session.state(7).problem)
        api.failure=HttpException(Response.error<Any>(422,"""{"detail":{"code":"unregistered_ingredients","names":["미등록"]}}""".toResponseBody()))
        session.request(original); advanceUntilIdle()
        assertEquals(listOf("미등록"),session.state(7).unknownNames)
        assertTrue(api.calls.none { it.second.ignoreUnregistered })
        api.failure=null; session.request(original,ignoreUnknown=true); advanceUntilIdle()
        assertTrue(api.calls.last().second.ignoreUnregistered)
        assertEquals(listOf("계란","미등록"),api.calls.last().second.ingredients)
    }
    @Test fun capabilityTimeoutIsRecoverableAndNeverCallsThePaidRoute()=runTest {
        val api=object: Fake(){override suspend fun selectedCapabilities():SelectedCapabilities {
            delay(4_000); return SelectedCapabilities(true)
        }}
        val session=SelectedRecipeSession(api,this)
        session.updateContext(RecipeContext(listOf("계란"))); session.request(original); advanceUntilIdle()
        assertEquals(SelectedProblem.TIMEOUT,session.state(7).problem)
        assertTrue(api.calls.isEmpty())
    }
    @Test fun providerFailuresAndRefusalKeepTheOriginalAndExposeTheirReason()=runTest {
        for((code,problem) in listOf("quota_exceeded" to SelectedProblem.QUOTA,
            "timeout" to SelectedProblem.TIMEOUT,"connection" to SelectedProblem.NETWORK,"configuration" to SelectedProblem.SERVER)) {
            val api=object: Fake(){override suspend fun reviseSelected(id:Long,request:SelectedRevisionRequest)=
                super.reviseSelected(id,request).copy(revision=RevisionOutcomeDto("failed",null,RevisionErrorDto(code))) }
            val session=SelectedRecipeSession(api,this)
            session.updateContext(RecipeContext(listOf("계란"))); session.request(original); advanceUntilIdle()
            assertEquals(problem,session.state(7).problem)
            assertEquals(original.steps,session.state(7).original!!.steps)
            assertNull(session.state(7).suggestion)
        }
        val api=object: Fake(){override suspend fun reviseSelected(id:Long,request:SelectedRevisionRequest)=
            super.reviseSelected(id,request).copy(revision=RevisionOutcomeDto("refused",RevisionResultDto("주재료 부족",emptyList(),null),null)) }
        val session=SelectedRecipeSession(api,this)
        session.updateContext(RecipeContext(listOf("계란"))); session.request(original); advanceUntilIdle()
        assertEquals(RevisionStatus.REFUSED,session.state(7).status)
        assertEquals("주재료 부족",session.state(7).message)
    }
    @Test fun aResponseForAnotherRecipeCannotBeAcceptedOrCached()=runTest {
        val api=object: Fake(){override suspend fun reviseSelected(id:Long,request:SelectedRevisionRequest)=super.reviseSelected(id+1,request)}
        val session=SelectedRecipeSession(api,this)
        session.updateContext(RecipeContext(listOf("계란"))); session.request(original); advanceUntilIdle()
        assertEquals(SelectedProblem.INVALID,session.state(7).problem)
        assertTrue(session.cachedOriginals.isEmpty())
    }
    @Test fun modelRequestTimeoutLeavesARecoverableState()=runTest {
        val api=object: Fake(){override suspend fun reviseSelected(id:Long,request:SelectedRevisionRequest):SelectedRevisionResponse {
            delay(91_000); return super.reviseSelected(id,request)
        }}
        val session=SelectedRecipeSession(api,this)
        session.updateContext(RecipeContext(listOf("계란"))); session.request(original); advanceUntilIdle()
        assertEquals(SelectedProblem.TIMEOUT,session.state(7).problem)
        assertEquals(RevisionStatus.ERROR,session.state(7).status)
    }
    @Test fun malformedNullStepCannotReachTheRecipeUi()=runTest {
        val api=object: Fake(){override suspend fun reviseSelected(id:Long,request:SelectedRevisionRequest):SelectedRevisionResponse {
            val json=Gson().toJsonTree(super.reviseSelected(id,request)).asJsonObject
            json.getAsJsonObject("revision").getAsJsonObject("result").getAsJsonObject("revised_recipe")
                .getAsJsonArray("steps")[0].asJsonObject.add("instruction",JsonNull.INSTANCE)
            return Gson().fromJson(json,SelectedRevisionResponse::class.java)
        }}
        val session=SelectedRecipeSession(api,this)
        session.updateContext(RecipeContext(listOf("계란"))); session.request(original); advanceUntilIdle()
        assertEquals(SelectedProblem.INVALID,session.state(7).problem)
        assertTrue(session.cachedOriginals.isEmpty())
    }
}
