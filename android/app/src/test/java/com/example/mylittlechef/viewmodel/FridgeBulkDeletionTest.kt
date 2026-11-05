package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.local.FridgeRepository
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class FridgeBulkDeletionTest {
    @Test fun bulkFailureKeepsInventoryAndRetryDeletesOnlyExactSelectedNames() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        var fail = true
        val finish = CompletableDeferred<Unit>()
        val source = object : FridgeRepository {
            override val names = MutableStateFlow(listOf("마늘", "다진마늘", "두부", "소금"))
            override suspend fun add(values: List<String>) = Unit
            override suspend fun remove(value: String) = error("Bulk must not loop over singleton writes")
            override suspend fun removeAll(values: Set<String>) {
                finish.await()
                if (fail) throw IOException("Disk failure")
                names.value = names.value.filterNot { it in values }
            }
        }
        try {
            val model = FridgeViewModel(source)
            var saved = false
            model.removeIngredients(setOf("마늘", "두부")) { saved = true }
            assertTrue(model.isRemovingIngredients)
            assertEquals(listOf("마늘", "다진마늘", "두부", "소금"), model.ingredients.map { it.name })
            model.removeIngredients(setOf("소금"))
            finish.complete(Unit)
            advanceUntilIdle()
            assertFalse(saved)
            assertNotNull(model.removalError)
            assertEquals(listOf("마늘", "다진마늘", "두부", "소금"), model.ingredients.map { it.name })
            fail = false
            model.removeIngredients(setOf("마늘", "두부")) { saved = true }
            advanceUntilIdle()
            assertTrue(saved)
            assertFalse(model.isRemovingIngredients)
            assertNull(model.removalError)
            assertEquals(listOf("다진마늘", "소금"), model.ingredients.map { it.name })
        } finally {
            finish.complete(Unit)
            advanceUntilIdle()
            Dispatchers.resetMain()
        }
    }
}
