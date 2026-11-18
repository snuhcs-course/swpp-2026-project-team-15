// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.dish

import com.example.mylittlechef.data.remote.ChangeDto
import com.example.mylittlechef.data.remote.DishRecipeApi
import com.example.mylittlechef.data.remote.RecipeIngredientDto
import com.example.mylittlechef.data.remote.RecipeStepDto
import com.example.mylittlechef.data.remote.RecipeViewRequest
import com.example.mylittlechef.data.remote.RecipeViewResponse
import com.example.mylittlechef.data.remote.RecipeVideoDto
import com.example.mylittlechef.data.remote.RevisedIngredientDto
import com.example.mylittlechef.data.remote.RevisedRecipeDto
import com.example.mylittlechef.data.remote.ReviseRequest
import com.example.mylittlechef.data.remote.ReviseResponse
import com.example.mylittlechef.data.remote.SourceRecipeDto
import com.example.mylittlechef.domain.Availability
import com.example.mylittlechef.domain.Revision
import com.example.mylittlechef.domain.toDishRecipe
import com.example.mylittlechef.domain.toRevision
import com.example.mylittlechef.viewmodel.DishRecipeSession
import com.example.mylittlechef.viewmodel.RecipeUiState
import com.example.mylittlechef.viewmodel.ReviseUiState
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class DishRecipeSessionTest {
    private lateinit var dispatcher: kotlinx.coroutines.test.TestDispatcher

    @Before fun setUp() { dispatcher = StandardTestDispatcher(); Dispatchers.setMain(dispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    private fun source() = SourceRecipeDto(
        "kimchi-fried-rice",
        RecipeVideoDto("abcdefghijk", "김치볶음밥", "채널"),
        2,
        listOf(RecipeIngredientDto("밥", "2공기", "main"), RecipeIngredientDto("대파", "1대", "secondary")),
        listOf(RecipeStepDto(1, "밥을 볶는다."), RecipeStepDto(2, "대파를 넣는다.")),
        listOf("신 김치가 좋다"),
        emptyList(),
        false
    )

    private fun view() = RecipeViewResponse("kimchi-fried-rice", "김치볶음밥", source(), listOf("owned", "unavailable"))

    private fun revised() = ReviseResponse(
        "revised", "kimchi-fried-rice",
        RevisedRecipeDto(2, listOf(RevisedIngredientDto("밥", "2공기")), listOf(RecipeStepDto(1, "밥을 볶는다.")), emptyList()),
        listOf(ChangeDto("대파가 없어서 뺐어요.", listOf(2), listOf(2))),
        null, null
    )

    private class FakeApi : DishRecipeApi {
        val recipeRequests = mutableListOf<RecipeViewRequest>()
        val reviseRequests = mutableListOf<ReviseRequest>()
        var onRecipe: suspend (RecipeViewRequest) -> RecipeViewResponse = { throw IOException() }
        var onRevise: suspend (ReviseRequest) -> ReviseResponse = { throw IOException() }
        override suspend fun recipe(request: RecipeViewRequest): RecipeViewResponse {
            recipeRequests += request
            return onRecipe(request)
        }
        override suspend fun revise(request: ReviseRequest): ReviseResponse {
            reviseRequests += request
            return onRevise(request)
        }
    }

    private fun http(code: Int) = HttpException(Response.error<Any>(code, "".toResponseBody("text/plain".toMediaType())))

    @Test fun recipeIsLoadedOnceAndSentWithTheFridge() = runTest(dispatcher) {
        val api = FakeApi().apply { onRecipe = { view() } }
        val session = DishRecipeSession(api, this) { listOf("밥", "김치") }
        session.requestRecipe("kimchi-fried-rice")
        assertTrue(session.recipeState("kimchi-fried-rice") is RecipeUiState.Loading)
        advanceUntilIdle()
        val ok = session.recipeState("kimchi-fried-rice") as RecipeUiState.Success
        assertEquals(listOf(Availability.OWNED, Availability.UNAVAILABLE), ok.recipe.ingredients.map { it.availability })
        assertTrue(ok.recipe.hasMissing)
        session.requestRecipe("kimchi-fried-rice")
        advanceUntilIdle()
        assertEquals(listOf(listOf("밥", "김치")), api.recipeRequests.map { it.ingredients })
    }

    @Test fun missingRecipeAndNetworkFailuresShowTheirOwnMessage() = runTest(dispatcher) {
        val api = FakeApi().apply { onRecipe = { throw http(404) } }
        val session = DishRecipeSession(api, this) { listOf("밥") }
        session.requestRecipe("x")
        advanceUntilIdle()
        assertEquals(DishRecipeSession.UNAVAILABLE_MESSAGE, (session.recipeState("x") as RecipeUiState.Error).message)
        api.onRecipe = { throw IOException() }
        session.requestRecipe("x") // an error is retried
        advanceUntilIdle()
        assertTrue((session.recipeState("x") as RecipeUiState.Error).message.contains("연결"))
        api.onRecipe = { view() }
        session.requestRecipe("x")
        advanceUntilIdle()
        assertTrue(session.recipeState("x") is RecipeUiState.Success)
    }

    @Test fun revisionReturnsRevisedRefusedAndFailedOutcomes() = runTest(dispatcher) {
        val api = FakeApi().apply { onRevise = { revised() } }
        val session = DishRecipeSession(api, this) { listOf("밥") }
        session.requestRevision("a")
        assertTrue(session.reviseState("a") is ReviseUiState.Loading)
        advanceUntilIdle()
        val done = (session.reviseState("a") as ReviseUiState.Done).revision as Revision.Revised
        assertEquals("대파가 없어서 뺐어요.", done.changes.single().reason)
        assertEquals(listOf(2), done.changes.single().ingredientRefs)

        api.onRevise = { ReviseResponse("refused", "a", null, null, "김치가 없으면 안 돼요.", null) }
        session.requestRevision("b")
        advanceUntilIdle()
        assertEquals(
            Revision.Refused("김치가 없으면 안 돼요."),
            (session.reviseState("b") as ReviseUiState.Done).revision
        )

        api.onRevise = { ReviseResponse("failed", "a", null, null, null, null) }
        session.requestRevision("c")
        advanceUntilIdle()
        assertTrue(((session.reviseState("c") as ReviseUiState.Done).revision) is Revision.Failed)
    }

    @Test fun serverErrorAndUnknownStatusOfARevisionAreRetryableErrors() = runTest(dispatcher) {
        val api = FakeApi().apply { onRevise = { throw http(502) } }
        val session = DishRecipeSession(api, this) { listOf("밥") }
        session.requestRevision("a")
        advanceUntilIdle()
        assertTrue(session.reviseState("a") is ReviseUiState.Error)
        api.onRevise = { ReviseResponse("???", "a", null, null, null, null) }
        session.requestRevision("a")
        advanceUntilIdle()
        assertEquals(DishRecipeSession.RETRY_MESSAGE, (session.reviseState("a") as ReviseUiState.Error).message)
        api.onRevise = { revised() }
        session.requestRevision("a")
        advanceUntilIdle()
        assertTrue(session.reviseState("a") is ReviseUiState.Done)
    }

    @Test fun anEmptyFridgeSendsNothing() = runTest(dispatcher) {
        val api = FakeApi().apply { onRevise = { revised() } }
        val session = DishRecipeSession(api, this) { emptyList() }
        session.requestRevision("a")
        advanceUntilIdle()
        assertNull(session.reviseState("a"))
        assertTrue(api.reviseRequests.isEmpty())
    }

    @Test fun clearingDropsAnswersAndIgnoresARunningRequest() = runTest(dispatcher) {
        val api = FakeApi().apply { onRevise = { revised() }; onRecipe = { view() } }
        val session = DishRecipeSession(api, this) { listOf("밥") }
        session.requestRecipe("a")
        session.requestRevision("a")
        session.clear() // the fridge changed before the answers arrived
        advanceUntilIdle()
        assertTrue(session.recipeState("a") is RecipeUiState.Loading || session.recipeState("a") == null)
        assertNull(session.reviseState("a"))
        session.open("a")
        session.reset()
        assertNull(session.openDishId)
    }

    @Test fun incompleteAnswersAreRejectedByTheMappers() {
        assertNull(view().copy(recipe = source().copy(steps = emptyList())).toDishRecipe())
        assertNull(view().copy(recipe = null).toDishRecipe())
        assertNull(revised().copy(revised = null).toRevision())
        assertNull(revised().copy(status = "other").toRevision())
        val recipe = view().toDishRecipe()!!
        assertEquals("채널", recipe.videoChannel)
        assertEquals(2, recipe.steps.size)
        assertEquals(false, recipe.fromVideo)
    }

    @Test fun recipesWrittenFromTheVideoAreMarkedAsSuch() {
        val recipe = view().copy(recipe = source().copy(source = "ai_structured_from_video")).toDishRecipe()!!
        assertTrue(recipe.fromVideo)
    }
}
