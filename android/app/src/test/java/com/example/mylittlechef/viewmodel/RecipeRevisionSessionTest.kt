package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.remote.*
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class RecipeRevisionSessionTest {
    private open class Fake : OnDemandRecipeApi {
        var calls = 0
        var status = "revised"
        var gate: CompletableDeferred<Unit>? = null
        val source = SourceRecipeDto(7, "Original", "10분", "2인분",
            listOf(SourceIngredientDto(1,"계란","2개"), SourceIngredientDto(2,"양파","1개")), listOf(SourceStepDto(1,"Original step")))
        override suspend fun recipeCatalog() = RecipeCatalogDto(listOf(
            CatalogItemDto(1,"계란",listOf("계란","달걀")), CatalogItemDto(2,"양파",listOf("양파"))))
        override suspend fun candidates(request: InventoryIdsDto) = CandidatesDto(listOf(CandidateDto(7,source,listOf(source.ingredients[1]),true)))
        override suspend fun reviseRecipe(id: Long, request: InventoryIdsDto): SingleRevisionDto {
            calls++
            if (status == "failed") return SingleRevisionDto(id,source,RevisionOutcomeDto("failed",null,RevisionErrorDto("rate_limit")))
            if (status == "refused") return SingleRevisionDto(id,source,RevisionOutcomeDto("refused",RevisionResultDto("Cannot adjust",emptyList(),null),null))
            gate?.let { withContext(NonCancellable) { it.await() } }
            return SingleRevisionDto(id,source,RevisionOutcomeDto("revised",RevisionResultDto("",listOf(RevisionChangeDto("omission","Skip onion")),
                RevisedRecipeDto("Revised","1인분",listOf(source.ingredients[0]),listOf(SourceStepDto(1,"Revised step")))),null))
        }
    }
    @Test fun listDoesNotReviseAndRepeatedExplicitRequestsReuseSession() = runTest {
        val api = Fake(); val session = RecipeRevisionSession(api, backgroundScope)
        session.updateContext(RecipeContext(listOf("달걀")))
        val originals = session.loadCandidates()
        assertEquals(0,api.calls)
        assertEquals("Original", originals.single().name)
        session.request(7); runCurrent()
        assertEquals(1,api.calls)
        assertEquals("Revised",session.state(7).recipe?.name)
        session.request(7); runCurrent()
        assertEquals(1,api.calls)
        assertEquals("Original", originals.single().name)
    }
    @Test fun contextChangeDropsResultsAndDiscardsLateResponse() = runTest {
        val api = Fake(); api.gate = CompletableDeferred()
        val session = RecipeRevisionSession(api, backgroundScope)
        session.updateContext(RecipeContext(listOf("계란")))
        session.loadCandidates(); session.request(7); runCurrent()
        session.request(7); assertEquals(1,api.calls)
        session.updateContext(RecipeContext(listOf("계란"),allergies=listOf("우유")))
        api.gate!!.complete(Unit); runCurrent()
        assertEquals(RevisionStatus.IDLE,session.state(7).status)
    }
    @Test fun unknownNameIsNotSilentlyDropped() = runTest {
        val session = RecipeRevisionSession(Fake(),backgroundScope)
        session.updateContext(RecipeContext(listOf("Unregistered")))
        try { session.loadCandidates(); fail("Expected visible mapping failure") }
        catch (error: IllegalArgumentException) { assertTrue(error.message!!.contains("Unregistered", ignoreCase = true)) }
    }
    @Test fun refusalIsReusedButOperationalFailureCanBeRetried() = runTest {
        val api = Fake(); api.status = "failed"
        val session = RecipeRevisionSession(api,backgroundScope)
        session.updateContext(RecipeContext(listOf("계란"))); session.loadCandidates()
        session.request(7); runCurrent()
        assertEquals(RevisionStatus.ERROR,session.state(7).status)
        assertTrue(session.state(7).message!!.contains("잠시"))
        api.status = "refused"; session.request(7); runCurrent()
        assertEquals(RevisionStatus.REFUSED,session.state(7).status)
        session.request(7); runCurrent(); assertEquals(2,api.calls)
        session.updateContext(RecipeContext(listOf("계란"),utensils=listOf("팬")))
        assertEquals(RevisionStatus.IDLE,session.state(7).status)
    }
    @Test fun equivalentContextOrderDoesNotInvalidateResult() = runTest {
        val api = Fake(); val session = RecipeRevisionSession(api,backgroundScope)
        session.updateContext(RecipeContext(listOf("계란"),allergies=listOf("우유","땅콩")))
        session.loadCandidates(); session.request(7); runCurrent()
        assertFalse(session.updateContext(RecipeContext(listOf(" 계란 ","계란"),allergies=listOf("땅콩","우유"))))
        assertEquals(RevisionStatus.REVISED,session.state(7).status)
    }
    @Test fun serverAssumedIngredientsAreNotReportedMissing() = runTest {
        val api = object : Fake() {
            override suspend fun candidates(request: InventoryIdsDto) = CandidatesDto(
                listOf(CandidateDto(7,source,listOf(source.ingredients[1]),true)),listOf(999))
            override suspend fun reviseRecipe(id: Long, request: InventoryIdsDto): SingleRevisionDto {
                val response = super.reviseRecipe(id,request)
                val result = response.revision.result!!
                val recipe = result.recipe!!
                return response.copy(revision = response.revision.copy(result = result.copy(
                    recipe = recipe.copy(ingredients = recipe.ingredients + SourceIngredientDto(999,"물",null)))))
            }
        }
        val session = RecipeRevisionSession(api,backgroundScope)
        session.updateContext(RecipeContext(listOf("계란"))); session.loadCandidates()
        session.request(7); runCurrent()
        assertEquals(emptyList<com.example.mylittlechef.model.Ingredient>(),session.state(7).recipe!!.missing)
    }
}
