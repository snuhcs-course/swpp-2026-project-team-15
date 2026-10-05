package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel

class UserViewModel : ViewModel()
{
    var nickname by mutableStateOf("")
        private set

    var utensils by mutableStateOf<List<String>>(emptyList())
        private set

    var allergies by mutableStateOf<List<String>>(emptyList())
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