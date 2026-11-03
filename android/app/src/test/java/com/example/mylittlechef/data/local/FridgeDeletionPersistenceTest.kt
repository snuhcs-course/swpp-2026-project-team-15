package com.example.mylittlechef.data.local

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class FridgeDeletionPersistenceTest {
    @get:Rule val folder = TemporaryFolder()

    @Test fun bulkRemovalIsOneTransactionAndPersistsExactNamesInArrivalOrder() = runBlocking {
        val file = folder.newFolder().resolve("bulk.preferences_pb")
        val job = SupervisorJob()
        var writes = 0
        val delegate = PreferenceDataStoreFactory.create(
            scope = CoroutineScope(Dispatchers.IO + job), produceFile = { file })
        val store = object : androidx.datastore.core.DataStore<androidx.datastore.preferences.core.Preferences> {
            override val data = delegate.data
            override suspend fun updateData(transform: suspend (androidx.datastore.preferences.core.Preferences) -> androidx.datastore.preferences.core.Preferences): androidx.datastore.preferences.core.Preferences {
                writes++
                return delegate.updateData(transform)
            }
        }
        try {
            val repository = PreferencesFridgeRepository(store)
            repository.add(listOf("마늘", "다진마늘", "두부", "소금"))
            writes = 0
            repository.removeAll(setOf("마늘", "두부"))
            assertEquals(1, writes)
            assertEquals(listOf("다진마늘", "소금"), repository.names.first())
        } finally { job.cancelAndJoin() }
        val reopenedJob = SupervisorJob()
        try {
            val repository = PreferencesFridgeRepository(PreferenceDataStoreFactory.create(
                scope = CoroutineScope(Dispatchers.IO + reopenedJob), produceFile = { file }))
            assertEquals(listOf("다진마늘", "소금"), repository.names.first())
        } finally { reopenedJob.cancelAndJoin() }
    }

    @Test fun deletedNameStaysDeletedAfterClosingAndReopeningTheStore() = runBlocking {
        val file = folder.newFolder().resolve("fridge.preferences_pb")
        val firstJob = SupervisorJob()
        try {
            val store = PreferenceDataStoreFactory.create(
                scope = CoroutineScope(Dispatchers.IO + firstJob), produceFile = { file })
            val repository = PreferencesFridgeRepository(store)
            repository.add(listOf("마늘", "다진마늘"))
            repository.remove("마늘")
            assertEquals(listOf("다진마늘"), repository.names.first())
        } finally {
            firstJob.cancelAndJoin()
        }
        val reopenedJob = SupervisorJob()
        try {
            val reopened = PreferencesFridgeRepository(PreferenceDataStoreFactory.create(
                scope = CoroutineScope(Dispatchers.IO + reopenedJob), produceFile = { file }))
            assertEquals(listOf("다진마늘"), reopened.names.first())
            reopened.remove("다진마늘")
            assertEquals(emptyList<String>(), reopened.names.first())
        } finally {
            reopenedJob.cancelAndJoin()
        }
    }
}
