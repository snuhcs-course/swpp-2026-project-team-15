// Ingredient name completion added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mylittlechef.data.remote.ApiClient
import com.example.mylittlechef.data.remote.IngredientSupportApi
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

class IngredientCatalogViewModel(
    private val api: IngredientSupportApi = ApiClient.api
) : ViewModel() {
    var names by mutableStateOf<List<String>>(emptyList())
        private set

    private var isLoading = false

    fun load() {
        if (names.isNotEmpty() || isLoading) return
        isLoading = true
        viewModelScope.launch {
            try {
                names = api.ingredientNames().names
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                // Manual entry remains available if the local server is offline.
            } finally {
                isLoading = false
            }
        }
    }
}
