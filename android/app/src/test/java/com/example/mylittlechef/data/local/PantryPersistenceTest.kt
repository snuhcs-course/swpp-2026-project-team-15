package com.example.mylittlechef.data.local

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class PantryPersistenceTest {
    @get:Rule val folder = TemporaryFolder()
    @Test fun pantrySelectionPersistsWithoutDroppingOtherIngredients() = runBlocking {
        val file = folder.newFolder().resolve("fridge.preferences_pb")
        val job = SupervisorJob()
        try {
            val repo = PreferencesFridgeRepository(PreferenceDataStoreFactory.create(
                scope = CoroutineScope(Dispatchers.IO + job), produceFile = { file }))
            repo.add(listOf("소금", "생강"))
            repo.replaceSelection(setOf("소금", "설탕"), listOf("설탕", "invalid"))
            assertEquals(listOf("생강", "설탕"), repo.names.first())
        } finally { job.cancelAndJoin() }
        val nextJob = SupervisorJob()
        try {
            val repo = PreferencesFridgeRepository(PreferenceDataStoreFactory.create(
                scope = CoroutineScope(Dispatchers.IO + nextJob), produceFile = { file }))
            assertEquals(listOf("생강", "설탕"), repo.names.first())
            repo.replaceSelection(setOf("소금", "설탕"), emptyList())
            assertEquals(listOf("생강"), repo.names.first())
        } finally { nextJob.cancelAndJoin() }
    }
}
