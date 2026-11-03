package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.local.FridgeRepository
import com.example.mylittlechef.model.Ingredient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class PantryIntegrationTest {
    @Test fun selectionOnlyChangesPresetNames() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val fridge = FridgeViewModel()
            fridge.addIngredients(listOf(Ingredient("소금"), Ingredient("생강")))
            fridge.updatePantryItems(listOf("설탕", "not-a-preset"))
            assertEquals(setOf("설탕", "생강"), fridge.ingredients.map { it.name }.toSet())
        } finally { Dispatchers.resetMain() }
    }

    @Test fun failedPantryWriteKeepsTheSavedInventory() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        val repository = object : FridgeRepository {
            override val names = MutableStateFlow(listOf("소금", "생강"))
            override suspend fun replaceSelection(options: Set<String>, selected: List<String>) { throw IOException("Disk unavailable") }
            override suspend fun add(values: List<String>) { throw IOException("Disk unavailable") }
            override suspend fun remove(value: String) { throw IOException("Disk unavailable") }
        }
        try {
            val fridge = FridgeViewModel(repository)
            fridge.updatePantryItems(listOf("설탕"))
            advanceUntilIdle()
            assertEquals(listOf("소금", "생강"), fridge.ingredients.map { it.name })
            assertNotNull(fridge.pantryError)
            assertFalse(fridge.isSavingPantry)
        } finally { Dispatchers.resetMain() }
    }
}
