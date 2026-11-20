// AI-assisted HE first-use help, 2026-11-09; manual review pending.
package com.example.mylittlechef.data.local

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.intPreferencesKey
import kotlinx.coroutines.flow.map

class UsageGuideRepository(private val store: DataStore<Preferences>) {
    companion object { const val CURRENT_VERSION = 1 }
    private val key = intPreferencesKey("usage_guide_version")
    val seenVersion = store.data.map { it[key] ?: 0 }
    suspend fun markSeen() {
        store.edit { it[key] = maxOf(it[key] ?: 0, CURRENT_VERSION) }
    }
}
