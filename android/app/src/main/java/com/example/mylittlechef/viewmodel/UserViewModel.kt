// AI-assisted with Codex (GPT-6.1 Sol), 2026-10-14; human review pending.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mylittlechef.data.local.UserRepository
import com.example.mylittlechef.domain.UserProfile
import kotlinx.coroutines.launch

class UserViewModel(
    private val repository: UserRepository? = null,
    nickname: String = "",
    utensils: List<String> = emptyList(),
    allergies: List<String> = emptyList()
) : ViewModel() {
    var nickname by mutableStateOf(nickname)
        private set

    var utensils by mutableStateOf(utensils)
        private set

    var allergies by mutableStateOf(allergies)
        private set

    var likes by mutableStateOf<List<Long>>(emptyList())
        private set

    var onboardingComplete by mutableStateOf(false)
        private set

    var isLoaded by mutableStateOf(repository == null)
        private set

    init {
        repository?.let { source ->
            viewModelScope.launch {
                source.profile.collect { profile ->
                    applyProfile(profile)
                    isLoaded = true
                }
            }
        }
    }

    private fun applyProfile(profile: UserProfile) {
        nickname = profile.nickname
        utensils = profile.utensils
        allergies = profile.allergies
        likes = profile.likes
        onboardingComplete = profile.onboardingComplete
    }

    private fun save(transform: (UserProfile) -> UserProfile) {
        repository?.let { source -> viewModelScope.launch { source.update(transform) } }
    }

    fun updateNickname(value: String) {
        nickname = value.trim()
        save { it.withNickname(value) }
    }

    fun updateUtensils(value: List<String>) {
        utensils = UserProfile().withUtensils(value).utensils
        save { it.withUtensils(value) }
    }

    fun updateAllergies(value: List<String>) {
        allergies = UserProfile().withAllergies(value).allergies
        save { it.withAllergies(value) }
    }

    fun addLikes(value: Long) {
        likes = (likes + value).distinct()
        save { it.like(value) }
    }

    fun removeLikes(value: Long) {
        likes = likes.filterNot { it == value }
        save { it.unlike(value) }
    }

    fun completeOnboarding() {
        onboardingComplete = true
        save { it.copy(onboardingComplete = true) }
    }
}
