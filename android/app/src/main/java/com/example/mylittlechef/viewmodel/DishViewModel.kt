// UAT stage 3 assisted by Codex, 2026-11-24; human review pending.
// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
// Usage events (dish_list, dish_open, player_error) added with Claude Code (Opus 5.5), 2026-11-20.
// Cooking-mode events (cook_start, cook_exit, cook_complete) added with Claude Code (Opus 5.5), 2026-11-26.
// Bookmarks, hide-for-this-list and in-list search for the #24 recipe UI added with Claude Code (Opus 5.5), 2026-11-20.
package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.domain.CookingTracker
import com.example.mylittlechef.domain.CookingUsage
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mylittlechef.data.local.FavoriteDish
import com.example.mylittlechef.data.local.FavoriteDishes
import com.example.mylittlechef.data.local.InMemoryFavoriteDishes
import com.example.mylittlechef.data.remote.DishApi
import com.example.mylittlechef.data.remote.DishApiClient
import com.example.mylittlechef.data.remote.DishRecipeApi
import com.example.mylittlechef.data.remote.DishSuggestRequest
import com.example.mylittlechef.data.remote.DishVideosRequest
import com.example.mylittlechef.domain.Dish
import com.example.mylittlechef.domain.ingredientDishes
import com.example.mylittlechef.domain.nextDishBatch
import com.example.mylittlechef.domain.DishSort
import com.example.mylittlechef.domain.DishVideo
import com.example.mylittlechef.domain.NoTelemetry
import com.example.mylittlechef.domain.Telemetry
import com.example.mylittlechef.domain.Usage
import com.example.mylittlechef.domain.UsageEvent
import com.example.mylittlechef.domain.failureCode
import com.example.mylittlechef.domain.sortDishes
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

/** The videos of one dish, found when its sheet opens. */
sealed interface VideoUiState {
    data object Loading : VideoUiState
    data class Success(val videos: List<DishVideo>) : VideoUiState
    data class Error(val message: String) : VideoUiState
}

data class DishRefreshFeedback(val id:Long,val changed:Boolean)

class DishViewModel(
    private val api: DishApi = DishApiClient.api,
    private val debounceMillis: Long = 400L,
    recipeApi: DishRecipeApi = DishApiClient.recipeApi,
    private val telemetry: Telemetry = NoTelemetry,
    private val favoriteStore: FavoriteDishes = InMemoryFavoriteDishes(),
    private val cooking: CookingTracker = CookingUsage(telemetry)
) : ViewModel(), CookingTracker by cooking {
    /** The recipe sheet and the revision of a dish; kept next to the dish list it opens from. */
    val recipes = DishRecipeSession(recipeApi, viewModelScope, telemetry) { lastNames.orEmpty() }

    var state by mutableStateOf<DishUiState>(DishUiState.EmptyFridge)
        private set
    var sort by mutableStateOf(DishSort.FEWEST_MISSING)
        private set
    /** Dish whose video sheet is open; lives here so a rotation keeps it. */
    var selectedDishId by mutableStateOf<String?>(null)
        private set

    private val videoStates = mutableStateMapOf<String, VideoUiState>()
    private var lastNames: List<String>? = null
    private var generation = 0L
    // Video lookup is independent of recommendation refreshes; only data reset invalidates it.
    private var videoEpoch = 0L
    private var job: Job? = null
    private var rawDishes: List<Dish> = emptyList()
    private var rawSource = ""
    private var batchIds:List<String> = emptyList()
    private var seenIds:Set<String> = emptySet()
    var refreshVersion by mutableStateOf(0L)
        private set
    private var refreshSequence=0L
    private var retryRefresh=false
    var refreshFeedback by mutableStateOf<DishRefreshFeedback?>(null)
        private set
    fun consumeRefreshFeedback(id:Long) {if(refreshFeedback?.id==id) refreshFeedback=null}
    fun relatedToIngredient(name:String):List<Dish> = ingredientDishes(rawDishes.filter {it.id !in hiddenIds},name)
    fun refreshSuggestions() {
        val names=lastNames?.takeIf {it.isNotEmpty()} ?: return
        if(state is DishUiState.Loading) return
        retryRefresh=true
        load(names,wait=false,refresh=true)
    }

    fun videoState(dishId: String): VideoUiState? = videoStates[dishId]

    /** Bookmarked dishes, kept on the phone (the server has no account to keep them). */
    var favorites by mutableStateOf<List<FavoriteDish>>(emptyList())
        private set
    /** Dishes hidden from this suggestion list only; a new list shows them again. */
    var hiddenIds by mutableStateOf<Set<String>>(emptySet())
        private set
    var lastHidden by mutableStateOf<String?>(null)
        private set
    /** The dish brought back by the last undo, so the list can scroll to it; a new value each time. */
    var restored by mutableStateOf<Restored?>(null)
        private set
    private var restoreCount = 0

    init {
        viewModelScope.launch { favoriteStore.dishes.collect { favorites = it } }
    }

    fun isFavorite(id: String) = favorites.any { it.id == id }

    /** True when the dish is in the current suggestions, so its missing list is known. */
    fun isSuggested(id: String) = rawDishes.any { it.id == id }

    fun toggleFavorite(dish: Dish) {
        viewModelScope.launch {
            if (isFavorite(dish.id)) favoriteStore.remove(dish.id)
            else favoriteStore.add(FavoriteDish(dish.id, dish.name, dish.thumbnailUrl))
        }
    }

    fun hide(id: String) {
        hiddenIds = hiddenIds + id
        lastHidden = id
    }

    fun undoHide() {
        val id = lastHidden ?: return
        hiddenIds = hiddenIds - id
        lastHidden = null
        restored = Restored(id, ++restoreCount)
    }

    /** The suggested dishes to show: not hidden, and whose name contains [query] (search within this list). */
    fun visibleSuggestions(query: String): List<Dish> {
        val current = (state as? DishUiState.Success)?.dishes
            ?: if(state is DishUiState.Loading || state is DishUiState.Error) sortDishes(rawDishes,sort) else emptyList()
        val q = query.trim()
        return current.filter { it.id !in hiddenIds && (if(q.isEmpty()) it.id in batchIds else it.name.contains(q, ignoreCase = true)) }
    }

    val showingPreviousSuggestions: Boolean
        get() = (state is DishUiState.Loading || state is DishUiState.Error) && rawDishes.isNotEmpty()

    /** Bookmarks as dishes: the current suggestion when it has one, else a card from what was kept. */
    fun favoriteDishes(): List<Dish> {
        val current = rawDishes.associateBy { it.id }
        return favorites.map { saved -> current[saved.id] ?: saved.asDish() }
    }

    /** The dish a detail screen shows, from the suggestions or the bookmarks. */
    fun dishById(id: String): Dish? =
        rawDishes.firstOrNull { it.id == id } ?: favorites.firstOrNull { it.id == id }?.asDish()

    private fun FavoriteDish.asDish() = Dish(
        id = id, name = name, category = "", have = emptyList(), missing = emptyList(), reason = "",
        searchUrl = com.example.mylittlechef.domain.DishLinks.safeSearchUrl(null, name),
        hasRecipe = true, thumbnailUrl = thumbnailUrl
    )

    fun selectDish(id: String?) {
        if (id != null && id != selectedDishId) telemetry.track(Usage(UsageEvent.DISH_OPEN, dishId = id))
        selectedDishId = id
    }

    /** The in-app player could not play a video of the dish (usage data only). */
    fun onPlayerError(dishId: String) {
        telemetry.track(Usage(UsageEvent.PLAYER_ERROR, dishId = dishId))
    }

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
        rawDishes=emptyList();batchIds=emptyList();seenIds=emptySet();retryRefresh=false;refreshFeedback=null
        load(cleaned, wait = true)
    }

    /** Forgets everything (data reset): running requests, answers, the selection and the last fridge. */
    fun resetState() {
        generation++
        videoEpoch++
        job?.cancel()
        videoStates.clear()
        recipes.reset()
        lastNames = null
        rawDishes = emptyList()
        rawSource = ""
        batchIds=emptyList();seenIds=emptySet();retryRefresh=false;refreshFeedback=null
        selectedDishId = null
        hiddenIds = emptySet()
        lastHidden = null
        state = DishUiState.EmptyFridge
    }

    fun retry() {
        val names = lastNames ?: return
        load(names, wait = false, refresh=retryRefresh)
    }

    private fun load(names: List<String>, wait: Boolean, refresh:Boolean=false) {
        val mine = ++generation
        job?.cancel()
        if(!refresh) {
            recipes.clear()
            hiddenIds = emptySet()
            lastHidden = null
        }
        if (names.isEmpty()) {
            rawDishes = emptyList()
            state = DishUiState.EmptyFridge
            return
        }
        state = DishUiState.Loading
        job = viewModelScope.launch {
            try {
                if (wait) delay(debounceMillis)
                val started = System.currentTimeMillis()
                val response = api.suggest(DishSuggestRequest(names))
                if (mine != generation) return@launch
                rawDishes = response.dishes.orEmpty().mapNotNull { it.toDish() }
                rawSource = response.source.orEmpty()
                val previous=batchIds
                val sorted=sortDishes(rawDishes,sort)
                if(refresh && rawDishes.all {it.id in seenIds}) seenIds=previous.toSet()
                batchIds=nextDishBatch(sorted,if(refresh) previous else emptyList(),if(refresh) seenIds else emptySet())
                seenIds=seenIds+batchIds
                if(refresh) {
                    hiddenIds=emptySet();lastHidden=null
                    refreshVersion++
                    refreshFeedback=DishRefreshFeedback(++refreshSequence,previous.toSet()!=batchIds.toSet())
                }
                retryRefresh=false
                telemetry.track(
                    Usage(
                        UsageEvent.DISH_LIST,
                        status = if (rawDishes.isEmpty()) "empty" else "ok",
                        count = rawDishes.size,
                        durationMs = System.currentTimeMillis() - started
                    )
                )
                state = if (rawDishes.isEmpty()) DishUiState.NoMatch
                else DishUiState.Success(sortDishes(rawDishes, sort), rawSource)
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                if (mine == generation) {
                    telemetry.track(Usage(UsageEvent.DISH_LIST, status = "error", code = failureCode(failure)))
                    state = DishUiState.Error(failureMessage(failure))
                }
            }
        }
    }

    /** Fetches the dish's videos once; an error is retried by calling this again. */
    fun requestVideos(dish: Dish) {
        val current = videoStates[dish.id]
        if (current is VideoUiState.Loading || current is VideoUiState.Success) return
        val mine = videoEpoch
        videoStates[dish.id] = VideoUiState.Loading
        viewModelScope.launch {
            try {
                val response = api.videos(DishVideosRequest(dish.id))
                if (mine == videoEpoch) {
                    videoStates[dish.id] = VideoUiState.Success(response.videos.orEmpty().mapNotNull { it.toVideo() })
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (failure: Exception) {
                if (mine == videoEpoch) videoStates[dish.id] = VideoUiState.Error(videoFailureMessage(failure))
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

/** A card brought back by "실행 취소"; [serial] makes two undos of the same dish distinct. */
data class Restored(val id: String, val serial: Int)
