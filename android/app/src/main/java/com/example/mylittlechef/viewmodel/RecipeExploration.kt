// AI-assisted HE exploration state, 2026-11-10; human review pending.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.*
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.model.Recipe
import kotlinx.coroutines.*
import retrofit2.HttpException

class RecipeExploration(private val api: RecipeExploreApi, private val scope: CoroutineScope,
    private val onUnsupported: () -> Unit = {},
    private val onRecipes: (List<Recipe>) -> Unit) {
    var supported by mutableStateOf<Boolean?>(null); private set
    var loading by mutableStateOf(false); private set
    var query by mutableStateOf(""); private set
    var hasMore by mutableStateOf(false); private set
    var error by mutableStateOf<String?>(null); private set
    var unregistered by mutableStateOf<List<UnregisteredIngredient>>(emptyList()); private set
    var hidden by mutableStateOf<Set<Long>>(emptySet()); private set
    var lastHidden by mutableStateOf<Long?>(null); private set
    var pageIds by mutableStateOf<Set<Long>>(emptySet()); private set
    private var generation = 0L
    private var job: Job? = null
    private var inventory = emptyList<String>()
    private var seen = emptySet<Long>()
    private var current = emptyList<Recipe>()
    fun load(names: List<String>, search: String = "", next: Boolean = false) {
        if(next && (loading || !hasMore)) return
        val version = ++generation
        job?.cancel()
        val reset = !next || inventory != names || query != search
        if(reset) { seen = emptySet(); hidden = emptySet(); lastHidden = null }
        inventory = names.toList(); query = search
        loading = true; error = null
        job = scope.launch {
            try {
                if(supported == null) supported = withTimeout(3_000) { api.exploreCapabilities().searchSupported }
                if(version != generation) return@launch
                if(supported != true) { onUnsupported(); return@launch }
                val response = api.explore(ExploreRequest(inventory, search, seen.toList()))
                if(version != generation) return@launch
                require(response.recipes.map { it.id }.distinct().size == response.recipes.size &&
                    response.recipes.none { it.id in seen }) { "중복된 레시피 응답을 받았어요. 다시 검색해 주세요." }
                current = response.recipes.map { it.toRecipe() }
                pageIds = current.map { it.id }.toSet()
                seen = seen + current.map { it.id }
                hasMore = response.hasMore; unregistered = response.unregistered
                onRecipes(current)
            } catch(timeout: TimeoutCancellationException) {
                if(version == generation) error = "서버 확인이 오래 걸리고 있어요. 다시 시도해 주세요."
            } catch(cancelled: CancellationException) { throw cancelled }
            catch(failure: Exception) {
                if(version != generation) return@launch
                if(failure is HttpException && failure.code() in setOf(404,405)) {
                    supported = false; hasMore = false; onUnsupported()
                } else error = recipeFailureMessage(failure)
            } finally { if(version == generation) loading = false }
        }
    }
    fun hide(id: Long) { hidden = hidden + id; lastHidden = id }
    fun undoHide() { lastHidden?.let { hidden = hidden - it }; lastHidden = null }
    fun invalidate() {
        generation++; job?.cancel(); loading = false; hasMore = false; error = null
        seen = emptySet(); hidden = emptySet(); lastHidden = null; unregistered = emptyList()
        pageIds = emptySet()
    }
}
