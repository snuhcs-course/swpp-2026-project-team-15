package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel

class UserViewModel(
    nickname: String = "",
    utensils: List<String> = emptyList(),
    allergies: List<String> = emptyList()
) : ViewModel()
{
    var nickname by mutableStateOf(nickname)
        private set

    var utensils by mutableStateOf<List<String>>(utensils)
        private set

    var allergies by mutableStateOf<List<String>>(allergies)
        private set

    fun updateNickname(value: String) {
        nickname = value
    }

    fun updateUtensils(value: List<String>) {
        utensils = value
    }

    fun updateAllergies(value: List<String>) {
        allergies = value
    }
}