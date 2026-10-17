// AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
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
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

class RecipeViewModel(
    private val api: MyLittleChefApi = ApiClient.api
) : ViewModel()
{
    var recommended by mutableStateOf<List<Recipe>>(emptyList())
        private set

    // Every recipe seen so far, so favorites and details survive a changed recommendation list.
    private val seen = mutableMapOf<Long, Recipe>()
    private var refreshJob: Job? = null

    fun refresh(fridge: List<Ingredient>) {
        // Only the latest fridge state may update the list.
        refreshJob?.cancel()
        refreshJob = viewModelScope.launch {
            val recipes = runCatching {
                api.recommend(RecommendRequest(fridge.map { it.name })).recipes.map { it.toRecipe() }
            }.getOrDefault(emptyList())
            recipes.forEach { seen[it.id] = it }
            recommended = recipes
        }
    }

    fun find(id: Long?): Recipe? = seen[id]

    fun liked(likes: List<Long>): List<Recipe> = likes.mapNotNull { seen[it] }
}
