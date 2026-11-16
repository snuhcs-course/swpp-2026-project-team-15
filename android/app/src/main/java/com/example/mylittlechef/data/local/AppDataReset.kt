// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data.local

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.io.File

/** Puts the app back to the state of a fresh install, as far as this device is concerned. */
interface AppDataReset {
    suspend fun resetAll()
}

/**
 * Clears every stored preference (fridge, nickname, utensils, allergies, likes, onboarding flag) except the
 * appearance setting, and deletes the photos and sweep frames in the cache. Nothing is sent to a server.
 */
class PreferencesAppDataReset(
    private val store: DataStore<Preferences>,
    private val cacheDir: File?
) : AppDataReset {
    // Same key as PreferencesThemeRepository; AppDataResetTest fails if the two ever drift apart.
    private val themeKey = stringPreferencesKey("appearance_theme_mode")

    override suspend fun resetAll() {
        store.edit { prefs ->
            val theme = prefs[themeKey]
            prefs.clear()
            if (theme != null) prefs[themeKey] = theme
        }
        cacheDir?.let { dir -> withContext(Dispatchers.IO) { CaptureCache.clear(dir) } }
    }
}
