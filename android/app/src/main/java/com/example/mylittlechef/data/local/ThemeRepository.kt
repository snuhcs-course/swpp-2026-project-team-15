// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.data.local

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.*
import com.example.mylittlechef.domain.ThemeMode
import kotlinx.coroutines.flow.catch
import kotlinx.coroutines.flow.map
import java.io.IOException

class PreferencesThemeRepository(private val store: DataStore<Preferences>) {
    private val key=stringPreferencesKey("appearance_theme_mode")
    val mode=store.data.catch { error ->
        if (error is IOException) emit(emptyPreferences()) else throw error
    }.map { preferences ->
        ThemeMode.entries.find { it.name == preferences[key] } ?: ThemeMode.SYSTEM
    }

    suspend fun set(mode: ThemeMode) { store.edit { it[key]=mode.name } }
}
