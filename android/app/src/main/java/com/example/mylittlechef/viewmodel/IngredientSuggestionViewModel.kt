// Ingredient suggestions added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mylittlechef.data.remote.ApiClient
import com.example.mylittlechef.data.remote.IngredientSuggestionDto
import com.example.mylittlechef.data.remote.IngredientSuggestionRequest
import com.example.mylittlechef.data.remote.IngredientSupportApi
import com.example.mylittlechef.model.Ingredient
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

class IngredientSuggestionViewModel(
    private val api: IngredientSupportApi = ApiClient.api
) : ViewModel() {
    var suggestions by mutableStateOf<List<IngredientSuggestionDto>>(emptyList())
        private set
    var isLoading by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set

    private var generation = 0L
    private var refreshJob: Job? = null

    fun refresh(fridge: List<Ingredient>) {
        val requestGeneration = ++generation
        refreshJob?.cancel()
        refreshJob = viewModelScope.launch {
            isLoading = true
            error = null
            try {
                val result = api.ingredientSuggestions(
                    IngredientSuggestionRequest(fridge.map { it.name })
                ).suggestions
                if (requestGeneration == generation) suggestions = result
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                if (requestGeneration != generation) return@launch
                suggestions = emptyList()
                error = "추천을 불러오지 못했어요. 서버 연결을 확인하고 다시 시도해 주세요."
            } finally {
                if (requestGeneration == generation) isLoading = false
            }
        }
    }
}
