// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.data.local

import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import com.example.mylittlechef.domain.ThemeMode
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class ThemeRepositoryTest {
    @get:Rule val folder=TemporaryFolder()

    @Test fun newInstallFollowsSystemAndExplicitModesResolveIndependently() {
        assertFalse(ThemeMode.SYSTEM.isDark(false)); assertTrue(ThemeMode.SYSTEM.isDark(true))
        assertFalse(ThemeMode.LIGHT.isDark(true)); assertTrue(ThemeMode.DARK.isDark(false))
    }

    @Test fun selectedThemeSurvivesStoreReopenAndCanReturnToSystem()=runBlocking {
        val file=folder.newFolder().resolve("appearance.preferences_pb")
        val job=SupervisorJob()
        try {
            val repository=PreferencesThemeRepository(PreferenceDataStoreFactory.create(
                scope=CoroutineScope(Dispatchers.IO+job),produceFile={file}))
            assertEquals(ThemeMode.SYSTEM,repository.mode.first())
            repository.set(ThemeMode.DARK)
            assertEquals(ThemeMode.DARK,repository.mode.first())
        } finally { job.cancelAndJoin() }
        val reopenedJob=SupervisorJob()
        try {
            val repository=PreferencesThemeRepository(PreferenceDataStoreFactory.create(
                scope=CoroutineScope(Dispatchers.IO+reopenedJob),produceFile={file}))
            assertEquals(ThemeMode.DARK,repository.mode.first())
            repository.set(ThemeMode.LIGHT); assertEquals(ThemeMode.LIGHT,repository.mode.first())
            repository.set(ThemeMode.SYSTEM); assertEquals(ThemeMode.SYSTEM,repository.mode.first())
        } finally { reopenedJob.cancelAndJoin() }
    }

    @Test fun unknownStoredValueFallsBackToSystem()=runBlocking {
        val job=SupervisorJob()
        try {
            val file=folder.newFolder().resolve("appearance.preferences_pb")
            val store=PreferenceDataStoreFactory.create(scope=CoroutineScope(Dispatchers.IO+job),produceFile={file})
            store.edit { it[stringPreferencesKey("appearance_theme_mode")]="unsupported-future-mode" }
            assertEquals(ThemeMode.SYSTEM,PreferencesThemeRepository(store).mode.first())
        } finally { job.cancelAndJoin() }
    }
}
