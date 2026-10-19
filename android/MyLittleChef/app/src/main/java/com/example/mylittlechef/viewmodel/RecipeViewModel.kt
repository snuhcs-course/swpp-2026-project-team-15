// AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
// Codex-assisted changes (GPT-6.1 Sol), 2026-10-14; human review pending.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mylittlechef.data.recipes.RecipeSource
import com.example.mylittlechef.data.recipes.RecipeBatch
import kotlinx.coroutines.CancellationException
import com.example.mylittlechef.data.remote.ApiClient
import com.example.mylittlechef.data.remote.MyLittleChefApi
import com.example.mylittlechef.data.remote.RecommendRequest
import com.example.mylittlechef.data.remote.toRecipe
import com.example.mylittlechef.domain.RecipeSortType
import com.example.mylittlechef.domain.sortRecipes
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

class RecipeViewModel(
    private val api: MyLittleChefApi = ApiClient.api,
    private val integrated: RecipeSource? = null
) : ViewModel() {
    var recommended by mutableStateOf<List<Recipe>>(emptyList())
        private set

    var sortType by mutableStateOf(RecipeSortType.RECOMMENDED)
        private set

    // Every recipe seen so far, so favorites and details survive a changed recommendation list.
    private val seen = mutableMapOf<Long, Recipe>()
    private var refreshJob: Job? = null
    private var generation = 0L
    private val restoring = mutableSetOf<Long>()
    private var restoredVersion by mutableStateOf(0)
    var isLoading by mutableStateOf(false)
        private set
    var errorMessage by mutableStateOf<String?>(null)
        private set
    var unmapped by mutableStateOf<List<String>>(emptyList())
        private set
    var favoriteError by mutableStateOf<String?>(null)
        private set

    fun refresh(fridge: List<Ingredient>) {
        val request = ++generation
        refreshJob?.cancel()
        isLoading = true
        errorMessage = null
        refreshJob = viewModelScope.launch {
            try {
                val batch = integrated?.recommend(fridge.map { it.name }) ?: RecipeBatch(
                    api.recommend(RecommendRequest(fridge.map { it.name })).recipes.map { it.toRecipe() }
                )
                if (request == generation) {
                    batch.recipes.forEach { seen[it.id] = it }
                    recommended = batch.recipes
                    unmapped = batch.unmapped
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                if (request == generation) {
                    recommended = emptyList()
                    unmapped = emptyList()
                    errorMessage = "추천을 불러오지 못했어요. 서버 연결과 재료 목록을 확인하고 다시 시도해 주세요."
                }
            } finally {
                if (request == generation) isLoading = false
            }
        }
    }

    fun restoreFavorites(ids: List<Long>) {
        val source = integrated ?: return
        ids.filter { it !in seen && it !in restoring }.forEach { id ->
            restoring += id
            viewModelScope.launch {
                try {
                    val original = source.original(id)
                    if (id !in seen) seen[id] = original
                    restoredVersion++
                    favoriteError = null
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (failure: Exception) {
                    favoriteError = "일부 즐겨찾기 원본을 불러오지 못했어요. 서버 연결을 확인해 주세요."
                } finally {
                    restoring -= id
                }
            }
        }
    }

    fun selectSort(value: RecipeSortType) {
        sortType = value
    }

    fun sortedRecommended(fridge: List<Ingredient>): List<Recipe> =
        sortRecipes(recommended, sortType, fridge.map { it.name })

    fun find(id: Long?): Recipe? { restoredVersion; return seen[id] }

    fun liked(likes: List<Long>, fridge: List<Ingredient> = emptyList()): List<Recipe> =
        sortRecipes(likes.mapNotNull { restoredVersion; seen[it] }, sortType, fridge.map { it.name })
}
