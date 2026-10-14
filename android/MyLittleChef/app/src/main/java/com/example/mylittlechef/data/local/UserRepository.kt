package com.example.mylittlechef.data.local

import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import com.example.mylittlechef.domain.UserProfile
import com.google.gson.Gson
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

interface UserRepository {
    val profile: Flow<UserProfile>
    suspend fun update(transform: (UserProfile) -> UserProfile)
}

class PreferencesUserRepository(private val store: DataStore<Preferences>) : UserRepository {
    private val gson = Gson()
    private val nicknameKey = stringPreferencesKey("user_nickname")
    private val utensilsKey = stringPreferencesKey("user_utensils")
    private val allergiesKey = stringPreferencesKey("user_allergies")
    private val likesKey = stringPreferencesKey("user_likes")
    private val onboardingKey = booleanPreferencesKey("user_onboarding_complete")

    private fun names(raw: String?): List<String> = try {
        gson.fromJson(raw ?: "[]", Array<String>::class.java)?.toList() ?: emptyList()
    } catch (_: Exception) {
        emptyList()
    }

    private fun ids(raw: String?): List<Long> = try {
        gson.fromJson(raw ?: "[]", Array<Long>::class.java)?.toList() ?: emptyList()
    } catch (_: Exception) {
        emptyList()
    }

    private fun read(prefs: Preferences) = UserProfile(
        nickname = prefs[nicknameKey] ?: "",
        utensils = names(prefs[utensilsKey]),
        allergies = names(prefs[allergiesKey]),
        likes = ids(prefs[likesKey]),
        onboardingComplete = prefs[onboardingKey] ?: false
    )

    override val profile: Flow<UserProfile> = store.data.map(::read)

    override suspend fun update(transform: (UserProfile) -> UserProfile) {
        store.edit { prefs ->
            val next = transform(read(prefs))
            prefs[nicknameKey] = next.nickname.trim()
            prefs[utensilsKey] = gson.toJson(next.withUtensils(next.utensils).utensils)
            prefs[allergiesKey] = gson.toJson(next.withAllergies(next.allergies).allergies)
            prefs[likesKey] = gson.toJson(next.likes.distinct())
            prefs[onboardingKey] = next.onboardingComplete
        }
    }
}
