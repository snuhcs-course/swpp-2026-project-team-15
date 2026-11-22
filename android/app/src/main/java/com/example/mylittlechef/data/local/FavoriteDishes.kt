// AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data.local

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringSetPreferencesKey
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.map

/**
 * A dish the user bookmarked, kept on the phone with what its card needs (the name and photo),
 * so the bookmark list shows it even when the current suggestions no longer contain it.
 */
data class FavoriteDish(val id: String, val name: String, val thumbnailUrl: String?)

interface FavoriteDishes {
    val dishes: Flow<List<FavoriteDish>>
    suspend fun add(dish: FavoriteDish)
    suspend fun remove(id: String)
}

/** Tests and previews: bookmarks live only in memory. */
class InMemoryFavoriteDishes : FavoriteDishes {
    override val dishes = MutableStateFlow<List<FavoriteDish>>(emptyList())
    override suspend fun add(dish: FavoriteDish) { dishes.value = dishes.value.filterNot { it.id == dish.id } + dish }
    override suspend fun remove(id: String) { dishes.value = dishes.value.filterNot { it.id == id } }
}

/** In the app's preferences, so a data reset (which clears them) also clears the bookmarks. */
class PreferencesFavoriteDishes(private val store: DataStore<Preferences>) : FavoriteDishes {
    private val key = stringSetPreferencesKey("favorite_dishes")

    override val dishes: Flow<List<FavoriteDish>> = store.data.map { prefs ->
        prefs[key].orEmpty().mapNotNull(::decode).sortedBy { it.name }
    }

    override suspend fun add(dish: FavoriteDish) {
        store.edit { prefs ->
            prefs[key] = prefs[key].orEmpty().filterNot { decode(it)?.id == dish.id }.toSet() + encode(dish)
        }
    }

    override suspend fun remove(id: String) {
        store.edit { prefs -> prefs[key] = prefs[key].orEmpty().filterNot { decode(it)?.id == id }.toSet() }
    }

    companion object {
        private const val SEP = "\u001F"
        fun encode(dish: FavoriteDish) = listOf(dish.id, dish.name, dish.thumbnailUrl.orEmpty()).joinToString(SEP)
        fun decode(value: String): FavoriteDish? {
            val parts = value.split(SEP)
            if (parts.size != 3 || parts[0].isBlank() || parts[1].isBlank()) return null
            return FavoriteDish(parts[0], parts[1], parts[2].ifBlank { null })
        }
    }
}
