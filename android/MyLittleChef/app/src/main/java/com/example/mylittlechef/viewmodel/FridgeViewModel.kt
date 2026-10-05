package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import com.example.mylittlechef.model.Ingredient

class FridgeViewModel : ViewModel()
{
    var ingredients by mutableStateOf<List<Ingredient>>(emptyList())
}