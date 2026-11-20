// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
// Usage events (recipe_view, revise) added with Claude Code (Opus 5.5), 2026-11-20.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import com.example.mylittlechef.data.remote.DishRecipeApi
import com.example.mylittlechef.data.remote.RecipeViewRequest
import com.example.mylittlechef.data.remote.ReviseRequest
import com.example.mylittlechef.domain.DishRecipe
import com.example.mylittlechef.domain.NoTelemetry
import com.example.mylittlechef.domain.Telemetry
import com.example.mylittlechef.domain.Usage
import com.example.mylittlechef.domain.UsageEvent
import com.example.mylittlechef.domain.failureCode
import com.example.mylittlechef.domain.Revision
import com.example.mylittlechef.domain.toDishRecipe
import com.example.mylittlechef.domain.toRevision
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.io.IOException

sealed interface RecipeUiState {
    data object Loading : RecipeUiState
    data class Success(val recipe: DishRecipe) : RecipeUiState
    data class Error(val message: String) : RecipeUiState
}

sealed interface ReviseUiState {
    data object Loading : ReviseUiState
    data class Done(val revision: Revision) : ReviseUiState
    data class Error(val message: String) : ReviseUiState
}

/**
 * The recipe sheet of the dish list: the stored recipe of the open dish and its revision to the fridge.
 * Both depend on what the fridge holds, so [clear] runs whenever the fridge changes.
 */
class DishRecipeSession(
    private val api: DishRecipeApi,
    private val scope: CoroutineScope,
    private val telemetry: Telemetry = NoTelemetry,
    private val fridge: () -> List<String>
) {
    var openDishId by mutableStateOf<String?>(null)
        private set
    private val recipes = mutableStateMapOf<String, RecipeUiState>()
    private val revisions = mutableStateMapOf<String, ReviseUiState>()
    private var generation = 0L

    fun recipeState(dishId: String): RecipeUiState? = recipes[dishId]

    fun reviseState(dishId: String): ReviseUiState? = revisions[dishId]

    fun open(dishId: String) { openDishId = dishId }

    fun close() { openDishId = null }

    /** Forgets the answers (the fridge changed or the data was reset); a running request is ignored. */
    fun clear() {
        generation++
        recipes.clear()
        revisions.clear()
    }

    fun reset() {
        clear()
        openDishId = null
    }

    /** Loads the recipe once; an error is retried by calling this again. */
    fun requestRecipe(dishId: String) {
        val current = recipes[dishId]
        if (current is RecipeUiState.Loading || current is RecipeUiState.Success) return
        val mine = generation
        recipes[dishId] = RecipeUiState.Loading
        scope.launch {
            try {
                val recipe = api.recipe(RecipeViewRequest(dishId, fridge())).toDishRecipe()
                if (mine != generation) return@launch
                val status = if (recipe != null) "ok" else "error"
                telemetry.track(Usage(UsageEvent.RECIPE_VIEW, dishId = dishId, status = status))
                recipes[dishId] = if (recipe != null) RecipeUiState.Success(recipe)
                else RecipeUiState.Error(UNAVAILABLE_MESSAGE)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                if (mine == generation) {
                    telemetry.track(
                        Usage(UsageEvent.RECIPE_VIEW, dishId = dishId, status = "error", code = failureCode(failure))
                    )
                    recipes[dishId] = RecipeUiState.Error(failureMessage(failure))
                }
            }
        }
    }

    fun requestRevision(dishId: String) {
        if (revisions[dishId] is ReviseUiState.Loading) return
        val names = fridge()
        if (names.isEmpty()) return
        val mine = generation
        revisions[dishId] = ReviseUiState.Loading
        val started = System.currentTimeMillis()
        scope.launch {
            try {
                val revision = api.revise(ReviseRequest(dishId, names)).toRevision()
                if (mine != generation) return@launch
                val status = when (revision) {
                    is Revision.Revised -> "revised"
                    is Revision.Refused -> "refused"
                    is Revision.Failed -> "failed"
                    null -> "error"
                }
                telemetry.track(
                    Usage(UsageEvent.REVISE, dishId = dishId, status = status, durationMs = System.currentTimeMillis() - started)
                )
                revisions[dishId] = if (revision != null) ReviseUiState.Done(revision)
                else ReviseUiState.Error(RETRY_MESSAGE)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                if (mine == generation) {
                    telemetry.track(
                        Usage(
                            UsageEvent.REVISE,
                            dishId = dishId,
                            status = "error",
                            code = failureCode(failure),
                            durationMs = System.currentTimeMillis() - started
                        )
                    )
                    revisions[dishId] = ReviseUiState.Error(failureMessage(failure))
                }
            }
        }
    }

    companion object {
        const val UNAVAILABLE_MESSAGE = "이 요리의 레시피는 아직 준비되지 않았어요."
        const val RETRY_MESSAGE = "레시피를 불러오지 못했어요. 다시 시도해 주세요."

        fun failureMessage(failure: Exception): String = when {
            failure is HttpException && failure.code() == 404 -> UNAVAILABLE_MESSAGE
            failure is HttpException && failure.code() == 429 -> "요청이 많아요. 잠시 후 다시 시도해 주세요."
            failure is HttpException && failure.code() >= 500 -> "서버가 응답하지 못했어요. 잠시 후 다시 시도해 주세요."
            failure is IOException -> "서버에 연결하지 못했어요. 인터넷 연결을 확인하고 다시 시도해 주세요."
            else -> RETRY_MESSAGE
        }
    }
}
