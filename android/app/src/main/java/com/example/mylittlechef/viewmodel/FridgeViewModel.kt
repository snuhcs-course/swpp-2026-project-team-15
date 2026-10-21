// AI-assisted with Codex (GPT-6.1 Sol), 2026-10-14; human review pending.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mylittlechef.data.local.FridgeRepository
import com.example.mylittlechef.domain.FridgeInventory
import com.example.mylittlechef.model.Ingredient
import kotlinx.coroutines.launch

class FridgeViewModel(private val repository: FridgeRepository? = null) : ViewModel() {
    var ingredients by mutableStateOf<List<Ingredient>>(emptyList())
        private set

    var isLoaded by mutableStateOf(repository == null)
        private set

    init {
        repository?.let { source ->
            viewModelScope.launch {
                source.names.collect { names ->
                    ingredients = names.map(::Ingredient)
                    isLoaded = true
                }
            }
        }
    }

    fun addIngredients(items: List<Ingredient>) {
        val names = items.map { it.name }
        ingredients = FridgeInventory(ingredients.map { it.name }).addAll(names).names.map(::Ingredient)
        repository?.let { source -> viewModelScope.launch { source.add(names) } }
    }

    fun removeIngredient(name: String) {
        ingredients = FridgeInventory(ingredients.map { it.name }).remove(name).names.map(::Ingredient)
        repository?.let { source -> viewModelScope.launch { source.remove(name) } }
    }
}
