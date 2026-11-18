// HE ingredient/exploration changes assisted by Codex, 2026-11-10; human review pending.
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
    private val ingredientIds: Map<String, Int> = emptyMap(),
    exploreApi: com.example.mylittlechef.data.remote.RecipeExploreApi? = (api as? com.example.mylittlechef.data.remote.RecipeExploreApi)
        ?: if (api is com.example.mylittlechef.data.remote.DeployedRecipeApi) ApiClient.recipeExploreApi else null,
    selectedApi: com.example.mylittlechef.data.remote.SelectedRecipeApi? = (api as? com.example.mylittlechef.data.remote.SelectedRecipeApi)
        ?: if (api is com.example.mylittlechef.data.remote.DeployedRecipeApi) ApiClient.selectedRecipeApi else null
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
    private val selectedSession = selectedApi?.let { source ->
        SelectedRecipeSession(source,viewModelScope) { original ->
            seen[original.id] = original
            recommended = recommended.map { if(it.id == original.id) original.copy(imageRes=it.imageRes) else it }
        }
    }
    val usesSelectedRevision get() = selectedSession != null
    val supportsRevision: Boolean get() = selectedSession != null || revisionSession != null || cloudRevision != null
    val supportsBatchRevision: Boolean get() = cloudRevision != null
    val batchRevisionLoading: Boolean get() = cloudRevision?.loading == true
    val canRequestBatchRevision: Boolean get() = cloudRevision?.canRequest == true
    val batchRevisionMessage: String? get() = cloudRevision?.message
    fun requestBatchRevision() { cloudRevision?.request() }
    private var legacyLoading by mutableStateOf(false)
    private var legacyError by mutableStateOf<String?>(null)
    val isLoading: Boolean get() = legacyLoading || exploration?.loading == true
    val error: String? get() = exploration?.error ?: legacyError
    private var latestFridge = emptyList<Ingredient>()
    private var inventoryContext: RecipeContext? = null
    private var hasLoadedRecommendations = false
    var searchQuery by mutableStateOf(""); private set
    private var legacyHidden by mutableStateOf<Set<Long>>(emptySet())
    private var legacyLastHidden by mutableStateOf<Long?>(null)
    private val exploration = exploreApi?.let { source ->
        RecipeExploration(source, viewModelScope, onUnsupported = { refreshLegacy(latestFridge) }) { values ->
            recommended = mergeBatchResults(values,cachedRevisionOriginals())
            recommended.forEach { seen[it.id] = it }
            hasLoadedRecommendations = true
        }
    }
    val fullSearchSupported get() = exploration?.supported == true
    val hasMoreRecommendations get() = exploration?.hasMore == true
    val lastHiddenRecipe get() = if(fullSearchSupported) exploration?.lastHidden else legacyLastHidden
    val unregisteredIngredients: List<com.example.mylittlechef.data.remote.UnregisteredIngredient> get() =
        if(fullSearchSupported) exploration?.unregistered.orEmpty()
        else if(ingredientIds.isEmpty()) emptyList() else com.example.mylittlechef.domain.IngredientNames
            .resolve(latestFridge.map { it.name },ingredientIds).second.map {
                com.example.mylittlechef.data.remote.UnregisteredIngredient(it)
            }
    val catalogNames get() = ingredientIds.keys.sorted()
    val unregisteredForAI get() = cloudRevision?.unregisteredNames.orEmpty()
    fun requestBatchSkippingUnregistered() { cloudRevision?.request(omitUnknown = true) }
    fun search(value: String, fridge: List<Ingredient>) {
        searchQuery = value.trim(); hasLoadedRecommendations = false; exploration?.invalidate(); refresh(fridge)
    }
    fun cachedAiRecipes(fridge: List<Ingredient>): List<Recipe> = sortRecipes(
        (selectedSession?.cachedOriginals.orEmpty() + cloudRevision?.originals.orEmpty()
            .filter { cloudRevision?.state(it.id)?.status == RevisionStatus.REVISED })
            .distinctBy { it.id }.map { seen[it.id] ?: it },sortType,fridge.map { it.name })
    private fun cachedRevisionOriginals() = selectedSession?.cachedOriginals.orEmpty() + cloudRevision?.originals.orEmpty()
    fun otherRecommendations(fridge: List<Ingredient>) {
        if(fullSearchSupported) exploration?.load(fridge.map { it.name }, searchQuery, next = true)
    }
    fun hideRecipe(id: Long) {
        if(fullSearchSupported) exploration?.hide(id) else { legacyHidden = legacyHidden + id; legacyLastHidden = id }
    }
    fun undoHideRecipe() {
        if(fullSearchSupported) exploration?.undoHide()
        else { legacyLastHidden?.let { legacyHidden = legacyHidden - it }; legacyLastHidden = null }
    }
    private var userAllergies = emptyList<String>()
    private var userUtensils = emptyList<String>()

    fun updateUserContext(fridge: List<Ingredient>, allergies: List<String>, utensils: List<String>) {
        latestFridge = fridge.toList()
        userAllergies = allergies; userUtensils = utensils
        val context = RecipeContext(fridge.map { it.name }, allergies, utensils)
        selectedSession?.updateContext(context)
        val localChanged = revisionSession?.updateContext(context) == true
        val cloudChanged = cloudRevision?.updateContext(context) == true
        val contextChanged = inventoryContext != null && inventoryContext != context.canonical()
        inventoryContext = context.canonical()
        if (localChanged || cloudChanged || contextChanged) {
            hasLoadedRecommendations = false
            exploration?.invalidate(); legacyHidden = emptySet(); legacyLastHidden = null
            refreshGeneration++; refreshJob?.cancel(); legacyLoading = false; legacyError = null
            recommended = emptyList()
            seen.keys.toList().forEach { id -> seen[id] = seen.getValue(id).copy(availabilityKnown = false, revisionCandidate = false, revisionAvailable = false) }
        }
    }
    fun selectedRevisionState(id: Long) = selectedSession?.state(id)
    fun revisionState(id: Long): RevisionUiState {
        val selected = selectedSession?.state(id)?.takeIf { it.status != RevisionStatus.IDLE }
        return selected?.let { RevisionUiState(it.status,it.suggestion,it.message,it.changes.map { change -> change.reason }) }
            ?: cloudRevision?.state(id) ?: revisionSession?.state(id) ?: RevisionUiState()
    }
    fun requestRevision(id: Long, ignoreUnknown: Boolean = false) {
        if(selectedSession != null) find(id)?.let { selectedSession.request(it,ignoreUnknown) }
        else revisionSession?.request(id)
    }
    fun cancelRevision(id: Long) { selectedSession?.cancel(id) }
    private var refreshJob: Job? = null
    private var refreshGeneration = 0L

    fun refresh(fridge: List<Ingredient>) {
        updateUserContext(fridge, userAllergies, userUtensils)
        // Returning from detail is not a new browsing session.
        if(hasLoadedRecommendations && error == null) return
        if (exploration != null && exploration.supported != false) {
            refreshGeneration++; refreshJob?.cancel(); legacyLoading = false; legacyError = null
            exploration.load(fridge.map { it.name }, searchQuery)
            return
        }
        refreshLegacy(fridge)
    }

    private fun refreshLegacy(fridge: List<Ingredient>) {
        legacyHidden = emptySet(); legacyLastHidden = null
        val generation = ++refreshGeneration
        refreshJob?.cancel()
        legacyLoading = true; legacyError = null
        refreshJob = viewModelScope.launch {
            val recipes = try {
                revisionSession?.loadCandidates() ?: api.recommend(RecommendRequest(fridge.map { it.name })).recipes.map { it.toRecipe() }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                if (generation == refreshGeneration) legacyError = recipeFailureMessage(failure)
                emptyList()
            }
            // A provider can finish after cancellation; only the current inventory may win.
            if (generation != refreshGeneration) return@launch
            recommended = mergeBatchResults(recipes, cachedRevisionOriginals())
            recommended.forEach { seen[it.id] = it }
            hasLoadedRecommendations = legacyError == null
            legacyLoading = false
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
        sortRecipes(recommended.filter { recipe ->
            (!fullSearchSupported || recipe.id in exploration?.pageIds.orEmpty()) &&
            recipe.id !in (if(fullSearchSupported) exploration?.hidden.orEmpty() else legacyHidden) &&
                (searchQuery.isBlank() || com.example.mylittlechef.domain.IngredientNames.normalize(recipe.name)
                    .contains(com.example.mylittlechef.domain.IngredientNames.normalize(searchQuery)))
        }, sortType, fridge.map { it.name })

    fun find(id: Long?): Recipe? = seen[id]

    fun liked(likes: List<Long>, fridge: List<Ingredient> = emptyList()): List<Recipe> =
        sortRecipes(likes.mapNotNull { seen[it] }, sortType, fridge.map { it.name })
}
