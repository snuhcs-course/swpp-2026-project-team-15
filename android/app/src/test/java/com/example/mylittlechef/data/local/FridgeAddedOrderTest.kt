// AI-assisted with Codex, 2026-11-02; human review pending.
package com.example.mylittlechef.data.local

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.viewmodel.FridgeViewModel
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class FridgeAddedOrderTest {
    @get:Rule val folder = TemporaryFolder()

    @Test fun pantryEditsRetainExistingPositionsAndAppendOnlyNewNamesAcrossReload() = runBlocking {
        val file = folder.newFolder().resolve("fridge.preferences_pb")
        val job = SupervisorJob()
        try {
            val repo = PreferencesFridgeRepository(PreferenceDataStoreFactory.create(
                scope = CoroutineScope(Dispatchers.IO + job), produceFile = { file }))
            repo.add(listOf("소금", "두부", "마늘"))
            repo.replaceSelection(setOf("소금", "설탕"), listOf("설탕", "소금"))
            assertEquals(listOf("소금", "두부", "마늘", "설탕"), repo.names.first())
            repo.remove("두부")
            repo.add(listOf("두부"))
            assertEquals(listOf("소금", "마늘", "설탕", "두부"), repo.names.first())
        } finally { job.cancelAndJoin() }
        val nextJob = SupervisorJob()
        try {
            val repo = PreferencesFridgeRepository(PreferenceDataStoreFactory.create(
                scope = CoroutineScope(Dispatchers.IO + nextJob), produceFile = { file }))
            assertEquals(listOf("소금", "마늘", "설탕", "두부"), repo.names.first())
        } finally { nextJob.cancelAndJoin() }
    }

    @Test fun noRepositoryPantryEditAlsoKeepsExistingAddedOrder() {
        val vm = FridgeViewModel()
        vm.addIngredients(listOf("소금", "두부", "김치").map(::Ingredient))
        vm.updatePantryItems(listOf("김치", "두부", "소금"))
        assertEquals(listOf("소금", "두부", "김치"), vm.ingredients.map { it.name })
    }
}
