// AI-assisted with Codex, 2026-11-01; human review pending.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.mutableStateMapOf
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import kotlinx.coroutines.*
import retrofit2.HttpException
import java.util.Locale

data class RecipeContext(val names: List<String>, val allergies: List<String> = emptyList(), val utensils: List<String> = emptyList()) {
    fun canonical() = RecipeContext(normalize(names), normalize(allergies), normalize(utensils))
    private fun normalize(values: List<String>) = values.map { it.trim().lowercase(Locale.ROOT) }.filter { it.isNotEmpty() }.distinct().sorted()
}
enum class RevisionStatus { IDLE, LOADING, REVISED, REFUSED, ERROR }
data class RevisionUiState(val status: RevisionStatus = RevisionStatus.IDLE, val recipe: Recipe? = null,
    val message: String? = null, val changes: List<String> = emptyList())

fun recipeFailureMessage(error: Throwable): String = when ((error as? HttpException)?.code()) {
    429 -> "요청이 많아요. 잠시 후 다시 시도해 주세요."
    404 -> "현재 서버에서 이 기능을 사용할 수 없어요. 서버 버전을 확인해 주세요."
    409 -> "재고 조건이 바뀌었어요. 레시피 목록을 다시 확인해 주세요."
    422 -> "등록한 재료 정보를 확인해 주세요."
    else -> if (error is IllegalArgumentException) error.message ?: "재료 정보를 확인해 주세요."
        else "서버에 연결하지 못했어요. 잠시 후 다시 시도해 주세요."
}

class RecipeRevisionSession(private val api: OnDemandRecipeApi, private val scope: CoroutineScope) {
    private var context: RecipeContext? = null
    private var generation = 0L
    private var catalog: List<CatalogItemDto>? = null
    private var inventory: List<Int>? = null
    private var assumedIds = emptySet<Int>()
    private var originals = emptyMap<Long, CandidateDto>()
    private val states = mutableStateMapOf<Long, RevisionUiState>()
    private val jobs = mutableMapOf<Long, Job>()

    fun updateContext(value: RecipeContext): Boolean {
        val normalized = value.canonical()
        if (normalized == context) return false
        context = normalized
        generation++
        jobs.values.forEach { it.cancel() }; jobs.clear()
        states.clear(); inventory = null; assumedIds = emptySet(); originals = emptyMap()
        return true
    }
    fun state(id: Long) = states[id] ?: RevisionUiState()

    suspend fun loadCandidates(): List<Recipe> {
        val version = generation
        val snapshot = requireNotNull(context)
        val items = catalog ?: api.recipeCatalog().items.also { catalog = it }
        val unknown = snapshot.names.filter { name -> items.none { row -> (row.aliases + row.name).any { it.lowercase(Locale.ROOT) == name } } }
        require(unknown.isEmpty()) { "재료명을 확인해 주세요: ${unknown.joinToString(", ")}. 자동완성 목록에서 선택해 주세요." }
        val ids = items.filter { row -> (row.aliases + row.name).any { it.lowercase(Locale.ROOT) in snapshot.names } }.map { it.id }.distinct().sorted()
        val response = api.candidates(InventoryIdsDto(ids))
        if (generation != version) return emptyList()
        inventory = ids
        assumedIds = response.assumedIds.toSet()
        originals = response.recipes.associateBy { it.id }
        return response.recipes.map { it.original.toOriginal(it.missing, it.revisionCandidate) }
    }

    fun request(id: Long) {
        if (state(id).status in listOf(RevisionStatus.LOADING, RevisionStatus.REVISED, RevisionStatus.REFUSED)) return
        val candidate = originals[id]
        val ids = inventory
        if (candidate == null || ids == null || !candidate.revisionCandidate) {
            states[id] = RevisionUiState(RevisionStatus.ERROR, message = "레시피 목록을 현재 재고로 다시 확인해 주세요.")
            return
        }
        val version = generation
        states[id] = RevisionUiState(RevisionStatus.LOADING)
        jobs[id] = scope.launch {
            try {
                val response = api.reviseRecipe(id, InventoryIdsDto(ids))
                if (version != generation) return@launch
                require(response.id == id && response.original.id == id) { "레시피 응답을 확인할 수 없어요." }
                val outcome = response.revision
                states[id] = when (outcome.status) {
                    "revised" -> {
                        val result = requireNotNull(outcome.result)
                        val revised = requireNotNull(result.recipe)
                        val base = candidate.original.toOriginal(candidate.missing, true)
                        RevisionUiState(RevisionStatus.REVISED, base.copy(name = revised.name,
                            servingText = revised.servings,
                            ingredients = revised.ingredients.map { Ingredient(it.name) },
                            ingredientQuantities = revised.ingredients.map { it.quantity },
                            steps = revised.steps.sortedBy { it.number }.map { it.instruction },
                            missing = revised.ingredients.filter {
                                it.id !in ids && it.id !in (response.assumedIds ?: candidate.assumedIds ?: assumedIds)
                            }.map { Ingredient(it.name) }),
                            message = result.reason, changes = result.changes.map { it.reason })
                    }
                    "refused" -> RevisionUiState(RevisionStatus.REFUSED, message = outcome.result?.reason ?: "현재 재료로 조정하기 어려워요.")
                    else -> RevisionUiState(RevisionStatus.ERROR, message = when(outcome.error?.code) {
                        "rate_limit" -> "요청이 많아요. 잠시 후 다시 시도해 주세요."
                        "quota_exceeded" -> "AI 사용 한도에 도달했어요. 원본 레시피를 확인해 주세요."
                        "configuration", "authentication", "permission" -> "현재 AI 수정 기능을 사용할 수 없어요. 원본 레시피를 확인해 주세요."
                        else -> "AI 제안을 불러오지 못했어요. 원본을 확인하거나 다시 시도해 주세요."
                    })
                }
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (error: Exception) {
                if (version == generation) states[id] = RevisionUiState(RevisionStatus.ERROR, message = recipeFailureMessage(error))
            } finally { if (version == generation) jobs.remove(id) }
        }
    }
}
