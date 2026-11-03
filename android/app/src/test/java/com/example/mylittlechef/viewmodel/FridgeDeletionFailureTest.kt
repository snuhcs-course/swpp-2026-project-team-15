package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.local.FridgeRepository
import com.example.mylittlechef.model.Ingredient
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class FridgeDeletionFailureTest {
    @Test fun failedWriteKeepsTheIngredientAndAllowsRetry() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        var failWrite = true
        val repository = object : FridgeRepository {
            override val names = MutableStateFlow(listOf("두부", "김치"))
            override suspend fun add(values: List<String>) = Unit
            override suspend fun remove(value: String) {
                if (failWrite) throw IOException("Test disk failure")
                names.value = names.value.filterNot { it == value }
            }
        }
        try {
            val fridge = FridgeViewModel(repository)
            fridge.removeIngredient("두부")
            advanceUntilIdle()
            assertEquals(listOf(Ingredient("두부"), Ingredient("김치")), fridge.ingredients)
            assertNotNull(fridge.removalError)
            assertNull(fridge.removingIngredient)
            fridge.dismissRemovalError()
            assertNull(fridge.removalError)
            failWrite = false
            fridge.removeIngredient("두부")
            advanceUntilIdle()
            assertEquals(listOf(Ingredient("김치")), fridge.ingredients)
            assertNull(fridge.removalError)
            assertNull(fridge.removingIngredient)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test fun repeatedConfirmationDoesNotRemoveAnotherNameWhileSaving() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        val finish = CompletableDeferred<Unit>()
        val repository = object : FridgeRepository {
            override val names = MutableStateFlow(listOf("마늘", "다진마늘"))
            override suspend fun add(values: List<String>) = Unit
            override suspend fun remove(value: String) {
                finish.await()
                names.value = names.value.filterNot { it == value }
            }
        }
        try {
            val fridge = FridgeViewModel(repository)
            fridge.removeIngredient("마늘")
            fridge.removeIngredient("다진마늘")
            assertEquals("마늘", fridge.removingIngredient)
            finish.complete(Unit)
            advanceUntilIdle()
            assertEquals(listOf(Ingredient("다진마늘")), fridge.ingredients)
            assertEquals(listOf("다진마늘"), repository.names.value)
        } finally {
            finish.complete(Unit)
            advanceUntilIdle()
            Dispatchers.resetMain()
        }
    }
}
