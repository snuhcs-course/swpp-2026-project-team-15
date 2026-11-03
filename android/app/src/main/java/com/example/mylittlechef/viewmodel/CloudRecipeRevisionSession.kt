// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.*
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import kotlinx.coroutines.*

/** Explicit batch only. Never implies that the server revised a user-selected dish. */
class CloudRecipeRevisionSession(
    private val api: BatchRecipeApi,
    private val ingredientIds: Map<String, Int>,
    private val scope: CoroutineScope,
    private val onResults: (List<Recipe>) -> Unit
) {
    private var context: RecipeContext? = null
    private var generation = 0L
    private var job: Job? = null
    private val states = mutableStateMapOf<Long, RevisionUiState>()
    var originals by mutableStateOf<List<Recipe>>(emptyList())
        private set
    var loading by mutableStateOf(false)
        private set
    var message by mutableStateOf<String?>(null)
        private set
    val canRequest get() = !loading

    fun state(id: Long) = states[id] ?: RevisionUiState()

    fun updateContext(value: RecipeContext): Boolean {
        val normalized = value.canonical()
        if (context == normalized) return false
        context = normalized; generation++; job?.cancel(); job = null
        loading = false; message = null
        originals = emptyList(); states.clear()
        return true
    }

    fun request() {
        if (!canRequest) return
        val snapshot = context ?: return
        val aliases = mapOf("달걀" to "계란", "후춧가루" to "후추")
        val names = snapshot.names.map { aliases[it] ?: it }
        val unknown = names.filter { it !in ingredientIds }
        if (unknown.isNotEmpty()) {
            message = "AI 요청용 재료 ID를 확인할 수 없어요: ${unknown.joinToString(", ")}. 일반 레시피 목록은 계속 볼 수 있어요."
            return
        }
        val ids = names.map { ingredientIds.getValue(it) }.distinct().sorted()
        val version = generation
        loading = true; message = null
        job = scope.launch {
            try {
                val response = api.recommendations(BatchRevisionRequest(ids, revisionLimit = 1))
                if (version != generation) return@launch
                require(response.recipes.all { it.id == it.original.id } &&
                    response.recipes.map { it.id }.distinct().size == response.recipes.size) {
                    "레시피 응답의 ID를 확인할 수 없어요."
                }
                // Compare only canonical IDs/names, never fuzzy-map or silently drop inventory.
                val canonicalNames = ingredientIds.entries.associate { (name, id) -> id to name }
                require(response.recipes.flatMap { it.original.ingredients }.all {
                    canonicalNames[it.id] == it.name
                }) { "앱과 서버의 재료 ID 목록이 달라요. 일반 레시피 목록을 이용해 주세요." }
                val attempted = response.recipes.filter { it.revision.status != "not_attempted" }
                val available = ids.toSet() + response.assumedIds
                val newStates = attempted.associate { entry ->
                    val base = entry.original.toOriginal(emptyList(), false)
                        .copy(imageUrl = resolveRecipeImageUrl(entry.mainImageUrl))
                    entry.id to outcomeState(entry.revision, base)
                }
                val revised = newStates.values.count { it.status == RevisionStatus.REVISED }
                val failure = response.summary.stoppedError ?: attempted.firstNotNullOfOrNull { it.revision.error }
                val newOriginals = attempted.map { entry ->
                    val missing = entry.original.ingredients.distinctBy { it.id }
                        .filter { it.id !in available }
                    entry.original.toOriginal(missing, false)
                        // The batch contract does not expose every per-recipe seasoning assumption.
                        // Keep original-list missing data when available; otherwise mark it unknown.
                        .copy(availabilityKnown = false, revisionAvailable = newStates[entry.id]?.status == RevisionStatus.REVISED,
                            imageUrl = resolveRecipeImageUrl(entry.mainImageUrl))
                }
                // A repeated explicit request updates returned dishes and preserves other cached suggestions.
                states.putAll(newStates)
                originals = (originals.associateBy { it.id } + newOriginals.associateBy { it.id }).values.toList()
                message = when {
                    failure != null -> revisionErrorMessage(failure.code)
                    revised > 0 -> "서버가 고른 레시피 ${revised}개의 AI 제안을 받았어요. 해당 레시피의 상세에서 확인해 주세요."
                    else -> "이번 요청에서는 AI 수정 제안이 없어요. 원본 레시피와 부족한 재료를 확인해 주세요."
                }
                onResults(originals)
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (error: Exception) {
                if (version == generation) message = recipeFailureMessage(error)
            } finally {
                if (version == generation) { loading = false; job = null }
            }
        }
    }

    private fun outcomeState(outcome: RevisionOutcomeDto, base: Recipe): RevisionUiState =
        when (outcome.status) {
            "revised" -> {
                val result = requireNotNull(outcome.result)
                val recipe = requireNotNull(result.recipe)
                RevisionUiState(RevisionStatus.REVISED, base.copy(name = recipe.name,
                    servingText = recipe.servings,
                    ingredients = recipe.ingredients.map { Ingredient(it.name) },
                    ingredientQuantities = recipe.ingredients.map { it.quantity },
                    steps = recipe.steps.sortedBy { it.number }.map { it.instruction },
                    // Successful server validation is authoritative; do not guess all-mode assumptions.
                    missing = emptyList()), result.reason, result.changes.map { it.reason })
            }
            "refused" -> RevisionUiState(RevisionStatus.REFUSED, message = outcome.result?.reason ?: "현재 재료로 조정하기 어려워요.")
            else -> RevisionUiState(RevisionStatus.ERROR, message = revisionErrorMessage(outcome.error?.code))
        }
}

private fun revisionErrorMessage(code: String?) = when (code) {
    "rate_limit" -> "요청이 많아요. 잠시 후 다시 시도해 주세요."
    "quota_exceeded" -> "AI 사용 한도에 도달했어요. 원본 레시피를 확인해 주세요."
    "configuration", "authentication", "permission" -> "현재 서버의 AI 수정 기능을 사용할 수 없어요. 원본 레시피를 확인해 주세요."
    else -> "AI 제안을 불러오지 못했어요. 원본을 확인하거나 다시 시도해 주세요."
}
