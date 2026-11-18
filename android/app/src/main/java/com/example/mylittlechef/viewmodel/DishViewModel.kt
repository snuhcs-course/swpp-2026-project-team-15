// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mylittlechef.data.remote.DishAdaptRequest
import com.example.mylittlechef.data.remote.DishApi
import com.example.mylittlechef.data.remote.DishApiClient
import com.example.mylittlechef.data.remote.DishRecipeApi
import com.example.mylittlechef.data.remote.DishSuggestRequest
import com.example.mylittlechef.data.remote.DishVideosRequest
import com.example.mylittlechef.domain.Dish
import com.example.mylittlechef.domain.DishAdaptation
import com.example.mylittlechef.domain.DishSort
import com.example.mylittlechef.domain.DishVideo
import com.example.mylittlechef.domain.sortDishes
import com.example.mylittlechef.domain.toAdaptation
import com.example.mylittlechef.domain.toDish
import com.example.mylittlechef.domain.toVideo
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import retrofit2.HttpException
import java.io.IOException

sealed interface DishUiState {
    /** The fridge is empty: nothing to suggest from. */
    data object EmptyFridge : DishUiState
    data object Loading : DishUiState
    data class Success(val dishes: List<Dish>, val source: String) : DishUiState
    /** The server answered but found no dish for these ingredients. */
    data object NoMatch : DishUiState
    data class Error(val message: String) : DishUiState
}

/** What the dish sheet shows first: the videos or the substitution answer. */
enum class DishSheetMode { VIDEOS, ADAPT }

sealed interface AdaptUiState {
    data object Loading : AdaptUiState
    data class Success(val adaptation: DishAdaptation) : AdaptUiState
    data class Error(val message: String) : AdaptUiState
}

/** The videos of one dish, found when its sheet opens. */
sealed interface VideoUiState {
    data object Loading : VideoUiState
    data class Success(val videos: List<DishVideo>) : VideoUiState
    data class Error(val message: String) : VideoUiState
}

class DishViewModel(
    private val api: DishApi = DishApiClient.api,
    private val debounceMillis: Long = 400L,
    recipeApi: DishRecipeApi = DishApiClient.recipeApi
) : ViewModel() {
    /** The recipe sheet and the revision of a dish; kept next to the dish list it opens from. */
    val recipes = DishRecipeSession(recipeApi, viewModelScope) { lastNames.orEmpty() }

    var state by mutableStateOf<DishUiState>(DishUiState.EmptyFridge)
        private set
    var sort by mutableStateOf(DishSort.FEWEST_MISSING)
        private set
    /** Dish whose video sheet is open; lives here so a rotation keeps it. */
    var selectedDishId by mutableStateOf<String?>(null)
        private set

    private val adaptations = mutableStateMapOf<String, AdaptUiState>()
    private val videoStates = mutableStateMapOf<String, VideoUiState>()
    private var lastNames: List<String>? = null
    private var generation = 0L
    private var job: Job? = null
    private var rawDishes: List<Dish> = emptyList()
    private var rawSource = ""

    fun adaptState(dishId: String): AdaptUiState? = adaptations[dishId]

    fun videoState(dishId: String): VideoUiState? = videoStates[dishId]

    var selectedMode by mutableStateOf(DishSheetMode.VIDEOS)
        private set

    fun selectDish(id: String?, mode: DishSheetMode = DishSheetMode.VIDEOS) {
        selectedDishId = id
        selectedMode = mode
    }

    /** Hides a substitution answer (the user closes the AI box). */
    fun dismissAdapt(dishId: String) { adaptations.remove(dishId) }

    fun selectSort(value: DishSort) {
        sort = value
        val current = state
        if (current is DishUiState.Success) state = current.copy(dishes = sortDishes(rawDishes, value))
    }

    /** Call whenever the fridge changes; the same list again (tab switch, rotation) does nothing. */
    fun onFridgeChanged(names: List<String>) {
        val cleaned = names.map { it.trim() }.filter { it.isNotEmpty() }.distinct()
        if (cleaned == lastNames) return
        lastNames = cleaned
        load(cleaned, wait = true)
    }

    /** Forgets everything (data reset): running requests, answers, the selection and the last fridge. */
    fun resetState() {
        generation++
        job?.cancel()
        adaptations.clear()
        videoStates.clear()
        recipes.reset()
        lastNames = null
        rawDishes = emptyList()
        rawSource = ""
        selectedDishId = null
        selectedMode = DishSheetMode.VIDEOS
        state = DishUiState.EmptyFridge
    }

    fun retry() {
        val names = lastNames ?: return
        load(names, wait = false)
    }

    private fun load(names: List<String>, wait: Boolean) {
        val mine = ++generation
        job?.cancel()
        adaptations.clear() // substitutions depend on what the fridge holds
        recipes.clear()
        if (names.isEmpty()) {
            rawDishes = emptyList()
            state = DishUiState.EmptyFridge
            return
        }
        state = DishUiState.Loading
        job = viewModelScope.launch {
            try {
                if (wait) delay(debounceMillis)
                val response = api.suggest(DishSuggestRequest(names))
                if (mine != generation) return@launch
                rawDishes = response.dishes.orEmpty().mapNotNull { it.toDish() }
                rawSource = response.source.orEmpty()
                state = if (rawDishes.isEmpty()) DishUiState.NoMatch
                else DishUiState.Success(sortDishes(rawDishes, sort), rawSource)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                if (mine == generation) state = DishUiState.Error(failureMessage(failure))
            }
        }
    }

    /** Fetches the dish's videos once; an error is retried by calling this again. */
    fun requestVideos(dish: Dish) {
        val current = videoStates[dish.id]
        if (current is VideoUiState.Loading || current is VideoUiState.Success) return
        val mine = generation
        videoStates[dish.id] = VideoUiState.Loading
        viewModelScope.launch {
            try {
                val response = api.videos(DishVideosRequest(dish.id))
                if (mine == generation) {
                    videoStates[dish.id] = VideoUiState.Success(response.videos.orEmpty().mapNotNull { it.toVideo() })
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                if (mine == generation) videoStates[dish.id] = VideoUiState.Error(videoFailureMessage(failure))
            }
        }
    }

    fun requestAdapt(dish: Dish) {
        val names = lastNames ?: return
        if (adaptations[dish.id] is AdaptUiState.Loading) return
        val mine = generation
        adaptations[dish.id] = AdaptUiState.Loading
        viewModelScope.launch {
            try {
                val result = api.adapt(DishAdaptRequest(dish.id, names, dish.missing)).toAdaptation()
                if (mine == generation) adaptations[dish.id] = AdaptUiState.Success(result)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                if (mine == generation) adaptations[dish.id] = AdaptUiState.Error(failureMessage(failure))
            }
        }
    }

    companion object {
        fun videoFailureMessage(failure: Exception): String = when {
            failure is IOException -> "서버에 연결하지 못했어요. 인터넷 연결을 확인하고 다시 시도해 주세요."
            else -> "영상을 찾지 못했어요. 잠시 후 다시 시도해 주세요."
        }

        fun failureMessage(failure: Exception): String = when {
            failure is HttpException && failure.code() in listOf(404, 405) ->
                "서버가 아직 요리 추천을 지원하지 않아요. 서버 버전을 확인해 주세요."
            failure is HttpException && failure.code() == 429 ->
                "요청이 많아요. 잠시 후 다시 시도해 주세요."
            failure is HttpException && failure.code() >= 500 ->
                "요리 추천 서버가 응답하지 못했어요. 잠시 후 다시 시도해 주세요."
            failure is IOException ->
                "서버에 연결하지 못했어요. 인터넷 연결을 확인하고 다시 시도해 주세요."
            else -> "요리 추천을 불러오지 못했어요. 다시 시도해 주세요."
        }
    }
}
