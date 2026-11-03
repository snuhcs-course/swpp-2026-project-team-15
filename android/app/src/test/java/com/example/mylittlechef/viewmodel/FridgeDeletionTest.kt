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
import org.junit.Assert.assertEquals
import org.junit.Test

private class DelayedRemovalRepository : FridgeRepository {
    override val names = MutableStateFlow(listOf("두부", "김치"))
    val allowWrite = CompletableDeferred<Unit>()
    override suspend fun add(values: List<String>) { names.value = names.value + values }
    override suspend fun remove(value: String) {
        allowWrite.await()
        names.value = names.value.filterNot { it == value }
    }
}

@OptIn(ExperimentalCoroutinesApi::class)
class FridgeDeletionTest {
    @Test fun ingredientRemainsVisibleUntilRemovalIsPersisted() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        val repository = DelayedRemovalRepository()
        try {
            val fridge = FridgeViewModel(repository)
            fridge.removeIngredient("두부")
            assertEquals(listOf(Ingredient("두부"), Ingredient("김치")), fridge.ingredients)
            repository.allowWrite.complete(Unit)
            advanceUntilIdle()
            assertEquals(listOf(Ingredient("김치")), fridge.ingredients)
            assertEquals(listOf("김치"), repository.names.value)
        } finally {
            repository.allowWrite.complete(Unit)
            advanceUntilIdle()
            Dispatchers.resetMain()
        }
    }
}
