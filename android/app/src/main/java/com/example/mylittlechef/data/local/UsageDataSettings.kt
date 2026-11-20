// AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data.local

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import java.util.UUID

/** Data is sent only after the notice was seen and while the switch is on. */
data class UsageDataState(val enabled: Boolean = true, val noticeSeen: Boolean = false) {
    val sending get() = enabled && noticeSeen
}

interface UsageDataSettings {
    val state: Flow<UsageDataState>
    /** A random id for this install, made on first use; a data reset clears it, so a new one follows. */
    suspend fun installId(): String
    suspend fun setEnabled(enabled: Boolean)
    suspend fun markNoticeSeen()
}

class PreferencesUsageDataSettings(private val store: DataStore<Preferences>) : UsageDataSettings {
    private val idKey = stringPreferencesKey("usage_install_id")
    private val enabledKey = booleanPreferencesKey("usage_enabled")
    private val noticeKey = booleanPreferencesKey("usage_notice_seen")

    override val state: Flow<UsageDataState> = store.data.map {
        UsageDataState(enabled = it[enabledKey] ?: true, noticeSeen = it[noticeKey] ?: false)
    }

    override suspend fun installId(): String {
        store.data.first()[idKey]?.let { return it }
        var id = ""
        store.edit { prefs -> id = prefs[idKey] ?: UUID.randomUUID().toString().also { prefs[idKey] = it } }
        return id
    }

    override suspend fun setEnabled(enabled: Boolean) {
        store.edit { it[enabledKey] = enabled }
    }

    override suspend fun markNoticeSeen() {
        store.edit { it[noticeKey] = true }
    }
}
