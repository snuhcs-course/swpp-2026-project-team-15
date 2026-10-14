package com.example.mylittlechef.domain

data class UserProfile(
    val nickname: String = "",
    val utensils: List<String> = emptyList(),
    val allergies: List<String> = emptyList(),
    val likes: List<Long> = emptyList(),
    val onboardingComplete: Boolean = false
) {
    fun withNickname(value: String): UserProfile = copy(nickname = value.trim())
    fun withUtensils(value: List<String>): UserProfile = copy(utensils = distinctNames(value))
    fun withAllergies(value: List<String>): UserProfile = copy(allergies = distinctNames(value))
    fun like(id: Long): UserProfile = copy(likes = (likes + id).distinct())
    fun unlike(id: Long): UserProfile = copy(likes = likes.filterNot { it == id })
}
