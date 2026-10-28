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
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

class FridgeViewModel(private val repository: FridgeRepository? = null) : ViewModel() {
    var ingredients by mutableStateOf<List<Ingredient>>(emptyList())
        private set

    var isLoaded by mutableStateOf(repository == null)
        private set

    var removingIngredient by mutableStateOf<String?>(null)
        private set

    var removalError by mutableStateOf<String?>(null)
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
        val selectedName = name.trim()
        if (removingIngredient != null ||
            ingredients.none { it.name.equals(selectedName, ignoreCase = true) }) return

        removalError = null
        val source = repository
        if (source == null) {
            ingredients = FridgeInventory(ingredients.map { it.name }).remove(selectedName).names.map(::Ingredient)
            return
        }

        removingIngredient = selectedName
        viewModelScope.launch {
            try {
                // The repository flow updates the UI only after the write succeeds.
                source.remove(selectedName)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                removalError = "재료를 삭제하지 못했어요. 다시 시도해 주세요."
            } finally {
                removingIngredient = null
            }
        }
    }

    fun dismissRemovalError() {
        removalError = null
    }
}
