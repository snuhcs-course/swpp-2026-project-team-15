package com.example.mylittlechef.integration

import com.example.mylittlechef.data.recipes.*
import com.example.mylittlechef.model.*
import com.example.mylittlechef.viewmodel.RecipeViewModel
import com.example.mylittlechef.domain.RecipeSortType
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class RecipeFlowTest {
    private fun recipe(id: Long) = Recipe(id, "source$id", id.toInt(), 1, emptyList(), listOf("Cook"))

    @Test fun refreshSortErrorRetryAndFavoriteRestore() = runTest {
        Dispatchers.setMain(StandardTestDispatcher(testScheduler))
        try {
            var fail = false
            var requests = 0
            val source = object : RecipeSource {
                override suspend fun recommend(names: List<String>): RecipeBatch {
                    requests++
                    if (fail) error("transport failed")
                    return RecipeBatch(listOf(recipe(3), recipe(1)), listOf("unknown"))
                }
                override suspend fun original(id: Long) = recipe(id)
            }
            val vm = RecipeViewModel(integrated = source)
            vm.refresh(listOf(Ingredient("계란")))
            assertTrue(vm.isLoading)
            advanceUntilIdle()
            assertFalse(vm.isLoading)
            assertNull(vm.errorMessage)
            assertEquals(listOf("unknown"), vm.unmapped)
            vm.selectSort(RecipeSortType.COOKING_TIME)
            assertEquals(listOf(1L, 3L), vm.sortedRecommended(emptyList()).map { it.id })
            assertEquals(listOf(3L, 1L), vm.recommended.map { it.id })
            fail = true
            vm.refresh(emptyList()); advanceUntilIdle()
            assertNotNull(vm.errorMessage)
            assertTrue(vm.recommended.isEmpty())
            fail = false
            vm.refresh(emptyList()); advanceUntilIdle()
            assertNull(vm.errorMessage)
            vm.restoreFavorites(listOf(99)); advanceUntilIdle()
            assertEquals(99L, vm.liked(listOf(99)).single().id)
            assertEquals(3, requests) // Restoring original never invokes revision.
        } finally { Dispatchers.resetMain() }
    }

    @Test fun emptyResultIsNotTransportFailure() = runTest {
        Dispatchers.setMain(StandardTestDispatcher(testScheduler))
        try {
            val source = object : RecipeSource {
                override suspend fun recommend(names: List<String>) = RecipeBatch(emptyList())
                override suspend fun original(id: Long) = recipe(id)
            }
            val vm = RecipeViewModel(integrated = source)
            vm.refresh(emptyList()); advanceUntilIdle()
            assertNull(vm.errorMessage)
            assertTrue(vm.recommended.isEmpty())
            assertFalse(vm.isLoading)
        } finally { Dispatchers.resetMain() }
    }

    @Test fun obsoleteResponseCannotOverwriteNewInventoryResult() = runTest {
        Dispatchers.setMain(StandardTestDispatcher(testScheduler))
        try {
            val first = CompletableDeferred<RecipeBatch>()
            val second = CompletableDeferred<RecipeBatch>()
            var count = 0
            val source = object : RecipeSource {
                override suspend fun recommend(names: List<String>): RecipeBatch {
                    val response = if (++count == 1) first else second
                    return withContext(NonCancellable) { response.await() }
                }
                override suspend fun original(id: Long) = recipe(id)
            }
            val vm = RecipeViewModel(integrated = source)
            vm.refresh(listOf(Ingredient("old"))); runCurrent()
            vm.refresh(listOf(Ingredient("new"))); runCurrent()
            second.complete(RecipeBatch(listOf(recipe(2)))); runCurrent()
            first.complete(RecipeBatch(listOf(recipe(1)))); advanceUntilIdle()
            assertEquals(2L, vm.recommended.single().id)
            assertNull(vm.errorMessage)
            assertFalse(vm.isLoading)
        } finally { Dispatchers.resetMain() }
    }
}
