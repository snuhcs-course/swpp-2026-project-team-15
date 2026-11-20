// Modified with Claude Code (Opus 5.5), 2026-11-20: dropped the client name-rule case (see below).
// AI-assisted HE regressions, 2026-11-10; human review pending.
package com.example.mylittlechef.viewmodel

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import com.example.mylittlechef.data.local.PreferencesFridgeRepository
import com.example.mylittlechef.model.Ingredient
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
    // Removed 2026-11-20 (merge into the YouTube-based branch): the client-side name rules it tested
    // (IngredientNames, recipe-DB Recipe) are gone; the server's reviewed name table decides ownership.
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
