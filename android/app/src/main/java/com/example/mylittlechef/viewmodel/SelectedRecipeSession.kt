// AI-assisted selected-recipe lifecycle, 2026-11-10; human review pending.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.mutableStateMapOf
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.model.Recipe
import com.example.mylittlechef.model.Ingredient
import com.google.gson.JsonParser
import java.io.IOException
import java.net.SocketTimeoutException
import kotlinx.coroutines.*
import retrofit2.HttpException

enum class SelectedProblem { NETWORK, TIMEOUT, RATE_LIMIT, QUOTA, SERVER, UNREGISTERED, UNSUPPORTED, CANCELLED, INVALID, NOT_FOUND }
data class SelectedRevisionState(val status: RevisionStatus = RevisionStatus.IDLE,
    val original: Recipe? = null, val suggestion: Recipe? = null, val message: String? = null,
    val changes: List<RevisionChangeDto> = emptyList(), val problem: SelectedProblem? = null,
    val unknownNames: List<String> = emptyList(), val mode: String = "unknown")

class SelectedRecipeSession(private val api: SelectedRecipeApi, private val scope: CoroutineScope,
    private val onOriginal: (Recipe) -> Unit = {}) {
    private val states = mutableStateMapOf<Long,SelectedRevisionState>()
    private val jobs = mutableMapOf<Long,Job>()
    private val tokens = mutableMapOf<Long,Long>()
    private var sequence = 0L
    private var generation = 0L
    private var context: RecipeContext? = null
    private var capability: SelectedCapabilities? = null
    fun state(id: Long) = states[id] ?: SelectedRevisionState()
    val cachedOriginals: List<Recipe> get() = states.values.filter { it.status == RevisionStatus.REVISED }.mapNotNull { it.original }
    fun updateContext(value: RecipeContext) {
        val normalized = value.canonical()
        if(context == normalized) return
        context = normalized; generation++
        jobs.values.forEach { it.cancel() }; jobs.clear(); tokens.clear(); states.clear()
    }
    fun request(recipe: Recipe, ignoreUnknown: Boolean = false) {
        if(state(recipe.id).status in setOf(RevisionStatus.LOADING,RevisionStatus.REVISED)) return
        val snapshot = context ?: return
        val version = generation
        val token = ++sequence
        tokens[recipe.id] = token
        fun current() = generation == version && tokens[recipe.id] == token
        states[recipe.id] = SelectedRevisionState(RevisionStatus.LOADING,original=recipe)
        jobs[recipe.id] = scope.launch {
            var probing = true
            var mode = "unknown"
            fun failure(problem: SelectedProblem, names: List<String> = emptyList()) {
                if(current()) states[recipe.id] = SelectedRevisionState(RevisionStatus.ERROR,
                    original=recipe,problem=problem,message=problemMessage(problem),unknownNames=names,mode=mode)
            }
            try {
                val cap = capability?.takeIf { it.supported } ?: withTimeout(3_000) { api.selectedCapabilities() }
                if(!current()) return@launch
                mode = cap.mode.takeIf { it in setOf("mock","live") } ?: "unknown"
                if(!cap.supported) { failure(SelectedProblem.UNSUPPORTED); return@launch }
                capability = cap; probing = false
                states[recipe.id] = state(recipe.id).copy(mode=mode)
                val result = withTimeout(90_000) { api.reviseSelected(recipe.id,
                    SelectedRevisionRequest(snapshot.names,ignoreUnknown)) }
                if(!current()) return@launch
                require(result.id == recipe.id && result.original.id == recipe.id)
                require(!result.original.name.isNullOrBlank() &&
                    result.original.ingredients.all { !it.name.isNullOrBlank() } &&
                    result.original.steps.all { !it.instruction.isNullOrBlank() })
                val base = result.original.toOriginal(result.missing,false).copy(imageRes=recipe.imageRes,
                    imageUrl=resolveRecipeImageUrl(result.imageUrl) ?: recipe.imageUrl)
                require(base.ingredients.isNotEmpty() && base.steps.isNotEmpty())
                mode = result.mode.takeIf { it in setOf("mock","live") } ?: "unknown"
                val outcome = result.revision
                states[recipe.id] = when(outcome.status) {
                    "revised" -> {
                        val value = requireNotNull(outcome.result)
                        val revised = requireNotNull(value.recipe)
                        require(!revised.name.isNullOrBlank() && revised.ingredients.isNotEmpty() && revised.steps.isNotEmpty() &&
                            revised.ingredients.all { !it.name.isNullOrBlank() } &&
                            revised.steps.all { !it.instruction.isNullOrBlank() })
                        SelectedRevisionState(RevisionStatus.REVISED,
                            original=base.copy(revisionAvailable=true),
                            suggestion=base.copy(name=revised.name,servingText=revised.servings,
                                ingredients=revised.ingredients.map { Ingredient(it.name) },
                                ingredientQuantities=revised.ingredients.map { it.quantity },
                                steps=revised.steps.sortedBy { it.number }.map { it.instruction },missing=emptyList()),
                            message=value.reason,changes=value.changes,mode=mode)
                    }
                    "refused" -> SelectedRevisionState(RevisionStatus.REFUSED,original=base,
                        message=outcome.result?.reason?.takeIf { it.isNotBlank() } ?: "현재 재료로 조정하기 어려워요.",mode=mode)
                    else -> {
                        val problem = problemCode(outcome.error?.code)
                        SelectedRevisionState(RevisionStatus.ERROR,original=base,problem=problem,message=problemMessage(problem),mode=mode)
                    }
                }
                onOriginal(requireNotNull(state(recipe.id).original))
            } catch(timeout: TimeoutCancellationException) { failure(SelectedProblem.TIMEOUT) }
            catch(cancelled: CancellationException) { throw cancelled }
            catch(error: HttpException) {
                val names = if(error.code() == 422) unknownNames(error) else emptyList()
                failure(when(error.code()) {
                    404,405 -> if(probing) SelectedProblem.UNSUPPORTED else SelectedProblem.NOT_FOUND
                    422 -> if(names.isNotEmpty()) SelectedProblem.UNREGISTERED else SelectedProblem.INVALID
                    429 -> SelectedProblem.RATE_LIMIT
                    else -> SelectedProblem.SERVER
                },names)
            } catch(error: SocketTimeoutException) { failure(SelectedProblem.TIMEOUT) }
            catch(error: IOException) { failure(SelectedProblem.NETWORK) }
            catch(error: Exception) { failure(SelectedProblem.INVALID) }
            finally { if(current()) jobs.remove(recipe.id) }
        }
    }
    fun cancel(id: Long) {
        if(state(id).status != RevisionStatus.LOADING) return
        tokens[id] = ++sequence; jobs.remove(id)?.cancel()
        states[id] = state(id).copy(status=RevisionStatus.ERROR,problem=SelectedProblem.CANCELLED,
            message=problemMessage(SelectedProblem.CANCELLED))
    }
    private fun unknownNames(error: HttpException): List<String> = runCatching {
        val detail=JsonParser.parseString(error.response()?.errorBody()?.string().orEmpty()).asJsonObject
            .getAsJsonObject("detail")
        if(detail.get("code").asString != "unregistered_ingredients") emptyList()
        else detail.getAsJsonArray("names").map { it.asString }
    }.getOrDefault(emptyList())
}

private fun problemCode(code: String?) = when(code) {
    "rate_limit" -> SelectedProblem.RATE_LIMIT
    "quota_exceeded" -> SelectedProblem.QUOTA
    "timeout" -> SelectedProblem.TIMEOUT
    "connection" -> SelectedProblem.NETWORK
    else -> SelectedProblem.SERVER
}
private fun problemMessage(problem: SelectedProblem) = when(problem) {
    SelectedProblem.NETWORK -> "인터넷 연결을 확인하고 다시 시도해 주세요."
    SelectedProblem.TIMEOUT -> "응답이 오래 걸리고 있어요. 원본을 보거나 다시 시도해 주세요."
    SelectedProblem.RATE_LIMIT -> "요청이 많아요. 잠시 후 다시 시도해 주세요."
    SelectedProblem.QUOTA -> "AI 이용 한도에 도달했어요. 원본 레시피를 확인해 주세요."
    SelectedProblem.UNREGISTERED -> "등록된 재료와 연결되지 않은 이름이 있어요. 이름을 확인해 주세요."
    SelectedProblem.UNSUPPORTED -> "현재 서버는 이 요리의 개별 AI 제안을 지원하지 않아요. 원본 레시피를 이용해 주세요."
    SelectedProblem.CANCELLED -> "요청을 취소했어요. 원본 레시피는 그대로예요."
    SelectedProblem.NOT_FOUND -> "이 레시피를 찾을 수 없어요. 목록을 다시 불러와 주세요."
    SelectedProblem.INVALID -> "레시피나 재료 정보를 확인하지 못했어요. 원본을 확인해 주세요."
    SelectedProblem.SERVER -> "지금은 AI 제안을 받을 수 없어요. 원본을 보거나 잠시 후 다시 시도해 주세요."
}
