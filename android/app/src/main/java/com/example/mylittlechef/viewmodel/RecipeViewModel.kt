// Deployed batch revision integration assisted by Codex, 2026-11-03; human review pending.
// AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
// Codex-assisted changes (GPT-6.1 Sol), 2026-10-14; human review pending.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import com.example.mylittlechef.data.remote.OnDemandRecipeApi
import com.example.mylittlechef.data.remote.BatchRecipeApi
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
    private val api: MyLittleChefApi = ApiClient.api,
    ingredientIds: Map<String, Int> = emptyMap()
) : ViewModel() {
    var recommended by mutableStateOf<List<Recipe>>(emptyList())
        private set

    var sortType by mutableStateOf(RecipeSortType.RECOMMENDED)
        private set

    // Every recipe seen so far, so favorites and details survive a changed recommendation list.
    private val seen = mutableStateMapOf<Long, Recipe>()
    private val revisionSession = (api as? OnDemandRecipeApi)?.let { RecipeRevisionSession(it, viewModelScope) }
    private val cloudRevision = (api as? BatchRecipeApi)?.let {
        CloudRecipeRevisionSession(it, ingredientIds, viewModelScope) { results ->
            recommended = mergeBatchResults(recommended, results)
            recommended.forEach { recipe -> seen[recipe.id] = recipe }
        }
    }
    val supportsRevision: Boolean get() = revisionSession != null || cloudRevision != null
    val supportsBatchRevision: Boolean get() = cloudRevision != null
    val batchRevisionLoading: Boolean get() = cloudRevision?.loading == true
    val canRequestBatchRevision: Boolean get() = cloudRevision?.canRequest == true
    val batchRevisionMessage: String? get() = cloudRevision?.message
    fun requestBatchRevision() { cloudRevision?.request() }
    var isLoading by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set
    private var userAllergies = emptyList<String>()
    private var userUtensils = emptyList<String>()

    fun updateUserContext(fridge: List<Ingredient>, allergies: List<String>, utensils: List<String>) {
        userAllergies = allergies; userUtensils = utensils
        val context = RecipeContext(fridge.map { it.name }, allergies, utensils)
        val localChanged = revisionSession?.updateContext(context) == true
        val cloudChanged = cloudRevision?.updateContext(context) == true
        if (localChanged || cloudChanged) {
            refreshGeneration++; refreshJob?.cancel(); isLoading = false; error = null
            recommended = emptyList()
            seen.keys.toList().forEach { id -> seen[id] = seen.getValue(id).copy(availabilityKnown = false, revisionCandidate = false, revisionAvailable = false) }
        }
    }
    fun revisionState(id: Long) = cloudRevision?.state(id) ?: revisionSession?.state(id) ?: RevisionUiState()
    fun requestRevision(id: Long) { revisionSession?.request(id) }
    private var refreshJob: Job? = null
    private var refreshGeneration = 0L

    fun refresh(fridge: List<Ingredient>) {
        updateUserContext(fridge, userAllergies, userUtensils)
        val generation = ++refreshGeneration
        refreshJob?.cancel()
        isLoading = true; error = null
        refreshJob = viewModelScope.launch {
            val recipes = try {
                revisionSession?.loadCandidates() ?: api.recommend(RecommendRequest(fridge.map { it.name })).recipes.map { it.toRecipe() }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                if (generation == refreshGeneration) error = recipeFailureMessage(failure)
                emptyList()
            }
            // A provider can finish after cancellation; only the current inventory may win.
            if (generation != refreshGeneration) return@launch
            recommended = mergeBatchResults(recipes, cloudRevision?.originals.orEmpty())
            recommended.forEach { seen[it.id] = it }
            isLoading = false
        }
    }

    private fun mergeBatchResults(base: List<Recipe>, batch: List<Recipe>): List<Recipe> {
        val extras = batch.associateBy { it.id }
        return base.map { recipe ->
            extras[recipe.id]?.let { extra ->
                extra.copy(imageRes = recipe.imageRes, imageUrl = extra.imageUrl ?: recipe.imageUrl,
                    missing = recipe.missing, availabilityKnown = recipe.availabilityKnown)
            } ?: recipe
        } + batch.filter { candidate -> base.none { it.id == candidate.id } }
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
