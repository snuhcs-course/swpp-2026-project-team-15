// AI-assisted with Codex (GPT-6.1 Sol), 2026-10-14; human review pending.
package com.example.mylittlechef.data.local

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import com.example.mylittlechef.domain.FridgeInventory
import com.google.gson.Gson
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

interface FridgeRepository {
    val names: Flow<List<String>>
    suspend fun add(values: List<String>)
    suspend fun remove(value: String)
    suspend fun replaceSelection(options: Set<String>, selected: List<String>) {
        throw UnsupportedOperationException("Selection updates are not supported")
    }
}

class PreferencesFridgeRepository(private val store: DataStore<Preferences>) : FridgeRepository {
    private val gson = Gson()
    private val key = stringPreferencesKey("fridge_names")

    private fun read(raw: String?): List<String> = try {
        FridgeInventory(gson.fromJson(raw ?: "[]", Array<String>::class.java)?.toList() ?: emptyList()).names
    } catch (_: Exception) {
        emptyList()
    }

    override val names: Flow<List<String>> = store.data.map { read(it[key]) }

    override suspend fun add(values: List<String>) {
        store.edit { prefs ->
            prefs[key] = gson.toJson(FridgeInventory(read(prefs[key])).addAll(values).names)
        }
    }

    override suspend fun remove(value: String) {
        store.edit { prefs ->
            prefs[key] = gson.toJson(FridgeInventory(read(prefs[key])).remove(value).names)
        }
    }
    override suspend fun replaceSelection(options: Set<String>, selected: List<String>) {
        store.edit { prefs ->
            val retained = read(prefs[key]).filterNot { it in options }
            val desired = selected.filter { it in options }
            prefs[key] = gson.toJson(FridgeInventory(retained + desired).names)
        }
    }
}
