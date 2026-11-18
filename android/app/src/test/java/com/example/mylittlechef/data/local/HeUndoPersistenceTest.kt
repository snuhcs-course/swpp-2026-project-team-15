// AI-assisted HE persistence regressions, 2026-11-09; manual review pending.
package com.example.mylittlechef.data.local

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import com.example.mylittlechef.domain.RemovedInventoryItem
import com.example.mylittlechef.domain.UserProfile
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class HeUndoPersistenceTest {
    @get:Rule val folder = TemporaryFolder()

    @Test fun recoveryAndGuidePersistWithoutRewindingNewInventoryOrProfile() = runBlocking {
        val file = folder.newFolder().resolve("he.preferences_pb")
        val job = SupervisorJob()
        try {
            val store = PreferenceDataStoreFactory.create(scope = CoroutineScope(Dispatchers.IO + job), produceFile = { file })
            val fridge = PreferencesFridgeRepository(store)
            val user = PreferencesUserRepository(store)
            val guide = UsageGuideRepository(store)
            assertEquals(0, guide.seenVersion.first())
            user.update { UserProfile(nickname = "테스트", likes = listOf(114), onboardingComplete = true) }
            fridge.add(listOf("마늘", "다진마늘", "두부"))
            fridge.removeAll(setOf("마늘", "두부"))
            fridge.add(listOf("계란", "마늘"))
            fridge.restoreRemoved(listOf(RemovedInventoryItem("마늘", 0), RemovedInventoryItem("두부", 2)))
            assertEquals(listOf("다진마늘", "계란", "두부", "마늘"), fridge.names.first())
            guide.markSeen()
            assertEquals("테스트", user.profile.first().nickname)
            assertEquals(listOf(114L), user.profile.first().likes)
        } finally { job.cancelAndJoin() }
        val reopenedJob = SupervisorJob()
        try {
            val reopened = PreferenceDataStoreFactory.create(scope = CoroutineScope(Dispatchers.IO + reopenedJob), produceFile = { file })
            assertEquals(1, UsageGuideRepository(reopened).seenVersion.first())
            assertEquals(listOf("다진마늘", "계란", "두부", "마늘"), PreferencesFridgeRepository(reopened).names.first())
            assertTrue(PreferencesUserRepository(reopened).profile.first().onboardingComplete)
        } finally { reopenedJob.cancelAndJoin() }
    }
}
