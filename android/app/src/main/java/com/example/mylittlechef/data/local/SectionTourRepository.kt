// Versioned actual-screen tour assisted by Codex, 2026-11-19; human review pending.
package com.example.mylittlechef.data.local
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.*
import kotlinx.coroutines.flow.map
class SectionTourRepository(private val store: DataStore<Preferences>) {
    companion object { const val CURRENT_VERSION=1 }
    private val key=intPreferencesKey("section_tour_version")
    val seenVersion=store.data.map { it[key] ?: 0 }
    suspend fun markSeen() { store.edit { it[key]=maxOf(it[key] ?: 0,CURRENT_VERSION) } }
}
