// AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
// Codex-assisted changes (GPT-6.1 Sol), 2026-10-14; human review pending.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mylittlechef.data.remote.ApiClient
import com.example.mylittlechef.data.remote.MyLittleChefApi
import com.example.mylittlechef.data.remote.RecommendRequest
import com.example.mylittlechef.data.remote.toRecipe
import com.example.mylittlechef.domain.RecipeSortType
import com.example.mylittlechef.domain.sortRecipes
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

class RecipeViewModel(
    private val api: MyLittleChefApi = ApiClient.api
) : ViewModel() {
    var recommended by mutableStateOf<List<Recipe>>(emptyList())
        private set

    var sortType by mutableStateOf(RecipeSortType.RECOMMENDED)
        private set

    // Every recipe seen so far, so favorites and details survive a changed recommendation list.
    private val seen = mutableMapOf<Long, Recipe>()
    private var refreshJob: Job? = null
    private var refreshGeneration = 0L

    fun refresh(fridge: List<Ingredient>) {
        val generation = ++refreshGeneration
        refreshJob?.cancel()
        refreshJob = viewModelScope.launch {
            val recipes = try {
                api.recommend(RecommendRequest(fridge.map { it.name })).recipes.map { it.toRecipe() }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                emptyList()
            }
            // A provider can finish after cancellation; only the current inventory may win.
            if (generation != refreshGeneration) return@launch
            recipes.forEach { seen[it.id] = it }
            recommended = recipes
        }
    }

    fun selectSort(value: RecipeSortType) {
        sortType = value
    }

    fun sortedRecommended(fridge: List<Ingredient>): List<Recipe> =
        sortRecipes(recommended, sortType, fridge.map { it.name })

    fun find(id: Long?): Recipe? = seen[id]

    fun liked(likes: List<Long>, fridge: List<Ingredient> = emptyList()): List<Recipe> =
        sortRecipes(likes.mapNotNull { seen[it] }, sortType, fridge.map { it.name })
}
