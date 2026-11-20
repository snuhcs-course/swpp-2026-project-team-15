// AI-assisted HE regressions, 2026-11-09; manual review pending.
package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.local.FridgeRepository
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.domain.RemovedInventoryItem
import com.example.mylittlechef.domain.restoreInventoryNames
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class HeDeletionUndoTest {
    @Test fun restoreIsPersistenceFirstAndFailureCanBeRetried() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        val gate = CompletableDeferred<Unit>()
        var fail = true
        val source = object : FridgeRepository {
            override val names = MutableStateFlow(listOf("마늘", "다진마늘", "두부"))
            override suspend fun add(values: List<String>) { names.value = names.value + values }
            override suspend fun remove(value: String) = Unit
            override suspend fun removeAll(values: Set<String>) { names.value = names.value.filterNot { it in values } }
            override suspend fun restoreRemoved(items: List<RemovedInventoryItem>) {
                gate.await()
                if (fail) throw IOException("disk")
                names.value = restoreInventoryNames(names.value, items)
            }
        }
        try {
            val vm = FridgeViewModel(source)
            vm.removeIngredients(setOf("마늘"))
            advanceUntilIdle()
            val id = requireNotNull(vm.pendingRemoval).id
            source.add(listOf("계란"))
            vm.undoRemoval(id)
            assertTrue(vm.isRestoringIngredients)
            assertEquals(listOf("다진마늘", "두부", "계란"), vm.ingredients.map { it.name })
            vm.removeIngredients(setOf("두부"))
            gate.complete(Unit)
            advanceUntilIdle()
            assertNotNull(vm.undoError)
            assertNotNull(vm.pendingRemoval)
            assertEquals(listOf("다진마늘", "두부", "계란"), vm.ingredients.map { it.name })
            fail = false
            vm.undoRemoval(id)
            advanceUntilIdle()
            assertNull(vm.undoError)
            assertNull(vm.pendingRemoval)
            assertEquals(listOf("마늘", "다진마늘", "두부", "계란"), vm.ingredients.map { it.name })
        } finally { gate.complete(Unit); advanceUntilIdle(); Dispatchers.resetMain() }
    }
    @Test fun undoRestoresOnlyDeletedNamesAndKeepsLaterChanges() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val vm = FridgeViewModel()
            vm.addIngredients(listOf("마늘", "다진마늘", "두부").map(::Ingredient))
            vm.removeIngredients(setOf("마늘"))
            val receipt = requireNotNull(vm.pendingRemoval)
            vm.addIngredients(listOf(Ingredient("계란")))
            vm.undoRemoval(receipt.id)
            assertEquals(listOf("마늘", "다진마늘", "두부", "계란"), vm.ingredients.map { it.name })
            assertNull(vm.pendingRemoval)
        } finally { Dispatchers.resetMain() }
    }

    @Test fun failedDeletionDoesNotOfferUndoAndStaleReceiptCannotUndoNewDeletion() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val vm = FridgeViewModel()
            vm.addIngredients(listOf("마늘", "두부", "소금").map(::Ingredient))
            vm.removeIngredients(setOf("마늘"))
            val old = requireNotNull(vm.pendingRemoval)
            vm.removeIngredients(setOf("두부"))
            vm.undoRemoval(old.id)
            assertEquals(listOf("소금"), vm.ingredients.map { it.name })
            assertEquals(listOf("두부"), vm.pendingRemoval!!.items.map { it.name })
            val source = object : FridgeRepository {
                override val names = MutableStateFlow(listOf("두부"))
                override suspend fun add(values: List<String>) = Unit
                override suspend fun remove(value: String) = Unit
                override suspend fun removeAll(values: Set<String>) { throw IOException("disk") }
            }
            val failed = FridgeViewModel(source)
            failed.removeIngredients(setOf("두부"))
            advanceUntilIdle()
            assertNull(failed.pendingRemoval)
            assertEquals(listOf("두부"), failed.ingredients.map { it.name })
        } finally { Dispatchers.resetMain() }
    }
}
