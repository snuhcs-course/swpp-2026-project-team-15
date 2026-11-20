// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data.local

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import com.example.mylittlechef.domain.ThemeMode
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.File

class AppDataResetTest {
    @get:Rule val folder = TemporaryFolder()

    private fun cacheWith(vararg names: String): File = folder.newFolder().also { dir ->
        names.forEach { name ->
            if (name.endsWith("/")) File(dir, name).apply { mkdirs(); File(this, "frame-00.jpg").writeText("x") }
            else File(dir, name).writeText("x")
        }
    }

    @Test fun resetClearsUserDataAndTheScreenModeAndDeletesCapturedFiles() = runBlocking {
        val cache = cacheWith("capture_1700000000.jpg", "sweep-1700000001/", "keep.txt", "capture_old.png")
        val job = SupervisorJob()
        try {
            val store = PreferenceDataStoreFactory.create(scope = CoroutineScope(Dispatchers.IO + job),
                produceFile = { folder.newFolder().resolve("app.preferences_pb") })
            val fridge = PreferencesFridgeRepository(store)
            val user = PreferencesUserRepository(store)
            val theme = PreferencesThemeRepository(store)
            fridge.add(listOf("계란", "대파"))
            user.update { it.withNickname("지원").like(7L).copy(onboardingComplete = true) }
            theme.set(ThemeMode.DARK)

            PreferencesAppDataReset(store, cache).resetAll()

            assertEquals(emptyList<String>(), fridge.names.first())
            val profile = user.profile.first()
            assertEquals("", profile.nickname)
            assertEquals(emptyList<Long>(), profile.likes)
            assertFalse(profile.onboardingComplete)
            // The screen mode is cleared too, so it follows the system setting again.
            assertEquals(ThemeMode.SYSTEM, theme.mode.first())
            assertEquals(listOf("capture_old.png", "keep.txt"), cache.listFiles()!!.map { it.name }.sorted())
        } finally { job.cancelAndJoin() }
    }

    @Test fun resetWithoutACacheFolderStillClearsThePreferences() = runBlocking {
        val job = SupervisorJob()
        try {
            val store = PreferenceDataStoreFactory.create(scope = CoroutineScope(Dispatchers.IO + job),
                produceFile = { folder.newFolder().resolve("app.preferences_pb") })
            val fridge = PreferencesFridgeRepository(store)
            fridge.add(listOf("두부"))
            PreferencesAppDataReset(store, cacheDir = null).resetAll()
            assertTrue(fridge.names.first().isEmpty())
        } finally { job.cancelAndJoin() }
    }

    @Test fun captureCacheOnlyRemovesPhotosAndSweepFolders() {
        val cache = cacheWith("capture_5.jpg", "capture_6.jpg", "sweep-5/", "sweep-x/", "other.jpg", "image_picker_1.jpg")
        assertEquals(3, CaptureCache.clear(cache))
        assertEquals(listOf("image_picker_1.jpg", "other.jpg", "sweep-x"), cache.listFiles()!!.map { it.name }.sorted())
        assertEquals(0, CaptureCache.clear(File(cache, "missing")))
    }
}
