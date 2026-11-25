// UAT stage 1 assisted by Codex, 2026-11-24; human review pending.
// Atomic multi-selection deletion assisted by Codex, 2026-11-03; human review pending.
// Fridge presentation/sorting and arrival-order updates assisted by Codex, 2026-11-02; human review pending.
// AI-assisted with Codex (GPT-6.1 Sol), 2026-10-14; human review pending.
package com.example.mylittlechef.data.local

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import com.example.mylittlechef.domain.FridgeInventory
import com.example.mylittlechef.domain.RemovedInventoryItem
import com.example.mylittlechef.domain.restoreInventoryNames
import com.google.gson.Gson
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

data class AddedIngredient(val name: String, val token: String)
sealed interface AdditionResult {
    data class Added(val receipt: AddedIngredient): AdditionResult
    data class AlreadyOwned(val name: String): AdditionResult
}

interface FridgeRepository {
    suspend fun addSuggested(name: String, token: String): AdditionResult =
        throw UnsupportedOperationException("Tracked addition is not supported")
    suspend fun undoSuggested(receipt: AddedIngredient): Boolean =
        throw UnsupportedOperationException("Tracked undo is not supported")
    val names: Flow<List<String>>
    suspend fun add(values: List<String>)
    suspend fun remove(value: String)
    suspend fun removeAll(values: Set<String>) {
        throw UnsupportedOperationException("Bulk removal is not supported")
    }
    suspend fun restoreRemoved(items: List<RemovedInventoryItem>) {
        throw UnsupportedOperationException("Deletion recovery is not supported")
    }
    suspend fun replaceSelection(options: Set<String>, selected: List<String>) {
        throw UnsupportedOperationException("Selection updates are not supported")
    }
}

class PreferencesFridgeRepository(private val store: DataStore<Preferences>) : FridgeRepository {
    private val gson = Gson()
    private val key = stringPreferencesKey("fridge_names")

    private val ownersKey = stringPreferencesKey("fridge_addition_owners")
    private fun owners(prefs: Preferences): Map<String,String> = runCatching {
        gson.fromJson(prefs[ownersKey] ?: "{}", com.google.gson.JsonObject::class.java)
            .entrySet().associate { it.key to it.value.asString }
    }.getOrDefault(emptyMap())
    private fun write(prefs: androidx.datastore.preferences.core.MutablePreferences, names: List<String>,
        ownership: Map<String,String> = owners(prefs)) {
        prefs[key] = gson.toJson(names)
        prefs[ownersKey] = gson.toJson(ownership.filterKeys { it in names })
    }
    override suspend fun addSuggested(name: String, token: String): AdditionResult {
        val clean = name.trim()
        require(clean.isNotEmpty())
        var result: AdditionResult = AdditionResult.AlreadyOwned(clean)
        store.edit { prefs ->
            val current=read(prefs[key])
            val existing=current.firstOrNull { it.equals(clean,ignoreCase=true) }
            if(existing!=null) result=AdditionResult.AlreadyOwned(existing)
            else {
                write(prefs,FridgeInventory(current).addAll(listOf(clean)).names,owners(prefs)+(clean to token))
                result=AdditionResult.Added(AddedIngredient(clean,token))
            }
        }
        return result
    }
    override suspend fun undoSuggested(receipt: AddedIngredient): Boolean {
        var removed=false
        store.edit { prefs ->
            val current=read(prefs[key])
            if(owners(prefs)[receipt.name]==receipt.token && receipt.name in current) {
                write(prefs,current.filterNot { it==receipt.name });removed=true
            }
        }
        return removed
    }

    private fun read(raw: String?): List<String> = try {
        FridgeInventory(gson.fromJson(raw ?: "[]", Array<String>::class.java)?.toList() ?: emptyList()).names
    } catch (_: Exception) {
        emptyList()
    }

    override val names: Flow<List<String>> = store.data.map { read(it[key]) }

    override suspend fun add(values: List<String>) {
        store.edit { prefs ->
            write(prefs, FridgeInventory(read(prefs[key])).addAll(values).names)
        }
    }

    override suspend fun remove(value: String) {
        store.edit { prefs ->
            write(prefs, FridgeInventory(read(prefs[key])).remove(value).names)
        }
    }
    override suspend fun removeAll(values: Set<String>) {
        store.edit { prefs ->
            write(prefs, FridgeInventory(read(prefs[key])).removeAll(values).names)
        }
    }
    override suspend fun restoreRemoved(items: List<RemovedInventoryItem>) {
        store.edit { prefs ->
            write(prefs, restoreInventoryNames(read(prefs[key]), items), owners(prefs)-items.map { it.name }.toSet())
        }
    }
    override suspend fun replaceSelection(options: Set<String>, selected: List<String>) {
        store.edit { prefs ->
            write(prefs, FridgeInventory(read(prefs[key])).replaceSelection(options, selected).names, owners(prefs)-options)
        }
    }
}
