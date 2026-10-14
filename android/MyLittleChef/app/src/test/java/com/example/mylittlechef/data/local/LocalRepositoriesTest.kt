package com.example.mylittlechef.data.local

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.file.Files

class LocalRepositoriesTest {
    @Test fun fridge_addRemoveAndRecreateRepository() = runBlocking {
        val dir = Files.createTempDirectory("fridge-repo")
        val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
        try {
            val store = PreferenceDataStoreFactory.create(scope = scope, produceFile = { dir.resolve("fridge.preferences_pb").toFile() })
            val first = PreferencesFridgeRepository(store)
            first.add(listOf(" 두부 ", "두부", "김치"))
            val reopened = PreferencesFridgeRepository(store)
            assertEquals(listOf("두부", "김치"), reopened.names.first())
            reopened.remove("김치")
            assertEquals(listOf("두부"), first.names.first())
        } finally {
            scope.cancel()
        }
    }

    @Test fun userProfile_updatesPersistAndStartEmpty() = runBlocking {
        val dir = Files.createTempDirectory("user-repo")
        val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
        try {
            val store = PreferenceDataStoreFactory.create(scope = scope, produceFile = { dir.resolve("user.preferences_pb").toFile() })
            val repo = PreferencesUserRepository(store)
            assertEquals("", repo.profile.first().nickname)
            repo.update { it.withNickname(" 아윤 ").withUtensils(listOf("냄비")).withAllergies(listOf("우유")).like(7).copy(onboardingComplete = true) }
            val reopened = PreferencesUserRepository(store).profile.first()
            assertEquals("아윤", reopened.nickname)
            assertEquals(listOf("냄비"), reopened.utensils)
            assertEquals(listOf("우유"), reopened.allergies)
            assertEquals(listOf(7L), reopened.likes)
            assertTrue(reopened.onboardingComplete)
        } finally {
            scope.cancel()
        }
    }
}
