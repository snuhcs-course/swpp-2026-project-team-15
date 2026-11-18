// AI-assisted lifecycle-safe persistence regressions, 2026-11-09; manual review pending.
package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.local.FridgeRepository
import com.example.mylittlechef.model.Ingredient
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class HeIngredientSaveStateTest {
    @Test fun completionIsPersistenceFirstOwnerScopedAndConsumedOnce() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        val gate = CompletableDeferred<Unit>()
        var writes = 0
        val source = object : FridgeRepository {
            override val names = MutableStateFlow(listOf("김치"))
            override suspend fun add(values: List<String>) { writes++; gate.await(); names.value = names.value + values }
            override suspend fun remove(value: String) = Unit
        }
        try {
            val vm = FridgeViewModel(source)
            vm.prepareIngredientEntry("first-screen")
            vm.saveIngredients(listOf(Ingredient("두부")), "first-screen")
            vm.saveIngredients(listOf(Ingredient("두부")), "first-screen")
            assertEquals(1, writes)
            assertTrue(vm.isSavingIngredients)
            assertNull(vm.ingredientSaveCompletion)
            assertEquals(listOf("김치"), vm.ingredients.map { it.name })
            gate.complete(Unit)
            advanceUntilIdle()
            val completion = requireNotNull(vm.ingredientSaveCompletion)
            assertFalse(vm.consumeIngredientSave(completion.copy(ownerId = "different-screen")))
            assertTrue(vm.consumeIngredientSave(completion))
            assertFalse(vm.consumeIngredientSave(completion))
            assertEquals(listOf("김치", "두부"), vm.ingredients.map { it.name })
        } finally { gate.complete(Unit); advanceUntilIdle(); Dispatchers.resetMain() }
    }

    @Test fun failedWriteHasNoCompletionAndCanBeRetriedWithoutLosingInventory() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        var fail = true
        val source = object : FridgeRepository {
            override val names = MutableStateFlow(listOf("김치"))
            override suspend fun add(values: List<String>) {
                if (fail) throw IOException("private disk detail")
                names.value = names.value + values
            }
            override suspend fun remove(value: String) = Unit
        }
        try {
            val vm = FridgeViewModel(source)
            vm.prepareIngredientEntry("screen")
            vm.saveIngredients(listOf(Ingredient("두부")), "screen")
            advanceUntilIdle()
            assertNull(vm.ingredientSaveCompletion)
            assertNotNull(vm.ingredientSaveError)
            assertEquals(listOf("김치"), vm.ingredients.map { it.name })
            fail = false
            vm.saveIngredients(listOf(Ingredient("두부")), "screen")
            advanceUntilIdle()
            assertNotNull(vm.ingredientSaveCompletion)
            assertNull(vm.ingredientSaveError)
        } finally { advanceUntilIdle(); Dispatchers.resetMain() }
    }
}
