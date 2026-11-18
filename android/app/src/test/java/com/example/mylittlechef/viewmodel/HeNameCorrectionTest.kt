// AI-assisted HE regressions, 2026-11-10; human review pending.
package com.example.mylittlechef.viewmodel

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import com.example.mylittlechef.data.local.PreferencesFridgeRepository
import com.example.mylittlechef.domain.IngredientNames
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test
import java.nio.file.Files

@OptIn(ExperimentalCoroutinesApi::class)
class HeNameCorrectionTest {
    @Test fun explicitNameCorrectionMergesWithExistingNameAndRetainsOtherInventory() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val vm=FridgeViewModel()
            vm.addIngredients(listOf(Ingredient("두푸"),Ingredient("두부"),Ingredient("우유")))
            vm.renameIngredient("두푸","두부")
            assertEquals(listOf("두부","우유"),vm.ingredients.map { it.name })
            vm.renameIngredient("없는 재료","대파")
            assertEquals(listOf("두부","우유"),vm.ingredients.map { it.name })
        } finally { Dispatchers.resetMain() }
    }
    @Test fun completionConnectsForwardFormsButNeverSelectsUnrelatedOrReverseForms() {
        val recipe=Recipe(1,"요리",10,1,listOf(Ingredient("다진 마늘"),Ingredient("달걀"),Ingredient("대파")),emptyList())
        assertEquals(listOf("마늘","계란"),IngredientNames.usedOwnedNames(recipe,
            listOf(Ingredient("마늘"),Ingredient("계란"),Ingredient("다진파"),Ingredient("우유"))))
    }
    @Test fun atomicCorrectionPersistsAfterReopeningTheStoreWithoutLosingOtherNames() = runBlocking {
        val directory=Files.createTempDirectory("he-name-correction")
        val file=directory.resolve("fridge.preferences_pb").toFile()
        val first=CoroutineScope(Dispatchers.IO+SupervisorJob())
        val second=CoroutineScope(Dispatchers.IO+SupervisorJob())
        try {
            val repo=PreferencesFridgeRepository(PreferenceDataStoreFactory.create(scope=first,produceFile={file}))
            repo.add(listOf("두푸","대파")); repo.add(listOf("우유"))
            repo.replaceSelection(setOf("두푸","두부"),listOf("두부"))
            first.cancel(); first.coroutineContext[Job]!!.join()
            val reopened=PreferencesFridgeRepository(PreferenceDataStoreFactory.create(scope=second,produceFile={file}))
            assertEquals(listOf("대파","우유","두부"),reopened.names.first())
        } finally {
            first.cancel(); second.cancel(); first.coroutineContext[Job]!!.join(); second.coroutineContext[Job]!!.join()
            file.delete(); directory.toFile().delete()
        }
    }
}
