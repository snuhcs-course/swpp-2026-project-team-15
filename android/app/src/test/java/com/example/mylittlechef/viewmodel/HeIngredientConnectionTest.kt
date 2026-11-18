// AI-assisted HE regressions, 2026-11-10; human review pending.
package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.remote.*
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class HeIngredientConnectionTest {
    @Test fun spacedNamesResolveAndForwardPreparationUsesCatalogIds() = runTest {
        val requests = mutableListOf<List<Int>>()
        val api = object : BatchRecipeApi {
            override suspend fun recommendations(request: BatchRevisionRequest): BatchRecommendationsDto {
                requests.add(request.ids)
                return BatchRecommendationsDto(emptyList(), emptyList(), BatchSummaryDto(1,0,0,null))
            }
        }
        val session = CloudRecipeRevisionSession(api, mapOf("마늘" to 1, "다진마늘" to 2, "계란" to 3), this) {}
        session.updateContext(RecipeContext(listOf(" 마 늘 ", "달 걀")))
        session.request(); advanceUntilIdle()
        assertEquals(listOf(listOf(1,2,3)), requests)
        session.updateContext(RecipeContext(listOf("다진 마늘")))
        session.request(); advanceUntilIdle()
        assertEquals(listOf(2), requests.last())
    }

    @Test fun unregisteredNameStillBlocksTheDefaultPaidRequest() = runTest {
        var called = false
        val api = object : BatchRecipeApi {
            override suspend fun recommendations(request: BatchRevisionRequest): BatchRecommendationsDto {
                called = true; error("Must not silently omit unknown inventory")
            }
        }
        val session = CloudRecipeRevisionSession(api, mapOf("계란" to 3), this) {}
        session.updateContext(RecipeContext(listOf("계란", "미등록")))
        session.request(); advanceUntilIdle()
        assertFalse(called)
        assertTrue(session.message!!.contains("미등록"))
    }
}
