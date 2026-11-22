// UX2 layout/lifecycle changes assisted by Codex, 2026-11-19; human review pending.
// AI-assisted HE photo review, 2026-11-09; manual review pending.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mylittlechef.domain.PhotoAnalysis
import com.example.mylittlechef.domain.PhotoAnalysisState
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.ui.fridge.components.IngredientEditorState
import kotlinx.coroutines.*
import retrofit2.HttpException
import java.io.FileNotFoundException
import java.io.IOException
import java.net.SocketTimeoutException

class PhotoAnalysisViewModel(private val load: suspend (String) -> PhotoAnalysis) : ViewModel() {
    val editor = IngredientEditorState()
    var state by mutableStateOf<PhotoAnalysisState>(PhotoAnalysisState.Loading)
        private set
    private var uri: String? = null
    private var started = false
    private var generation = 0L
    private var job: Job? = null
    private var confirmedRows by mutableStateOf<List<Ingredient>?>(null)
    val confirmed: Boolean get() = editor.ingredients.isNotEmpty() && confirmedRows == editor.ingredients.toList()

    fun confirm(value: Boolean) {
        if (value) editor.finishEdit()
        confirmedRows = if (value) editor.ingredients.toList() else null
    }

    private var entryToken: String? = null
    /** Rotation retains the token; deliberately reopening the same photo uses a new token. */
    fun startEntry(value: String?, token: String) {
        if (entryToken != token) { entryToken = token; started = false }
        start(value)
    }

    fun start(value: String?) {
        if (started && uri == value) return
        started = true
        uri = value
        retry()
    }

    fun retry() {
        val version = ++generation
        job?.cancel()
        confirmedRows = null
        editor.replaceAll(emptyList())
        val photo = uri
        if (photo.isNullOrBlank()) {
            state = PhotoAnalysisState.Failed("사진을 불러올 수 없어요. 다시 찍거나 직접 입력해 주세요.")
            return
        }
        state = PhotoAnalysisState.Loading
        job = viewModelScope.launch {
            try {
                val result = withTimeout(65_000) { load(photo) }
                if (version != generation) return@launch
                if (result.candidates.isEmpty()) state = PhotoAnalysisState.Empty(result)
                else {
                    editor.replaceAll(result.candidates)
                    state = PhotoAnalysisState.Ready(result)
                }
            } catch (_: TimeoutCancellationException) {
                if (version == generation) state = PhotoAnalysisState.Failed("인식 시간이 길어지고 있어요. 다시 시도해 주세요.")
            } catch (cancelled: CancellationException) { throw cancelled }
            catch (error: Exception) {
                if (version == generation) state = PhotoAnalysisState.Failed(photoAnalysisFailure(error))
            }
        }
    }

    fun cancel() {
        generation++
        job?.cancel()
        confirmedRows = null
        state = PhotoAnalysisState.Cancelled
    }

    override fun onCleared() { generation++; job?.cancel() }
}

fun photoAnalysisFailure(error: Throwable): String = when {
    error is SocketTimeoutException -> "응답이 늦어지고 있어요. 다시 시도해 주세요."
    error is HttpException -> when (error.code()) {
        413 -> "사진이 너무 커요. 사진을 한 장씩 다시 찍어 주세요."
        415, 422 -> "사진을 읽기 어려워요. 다시 찍거나 직접 입력해 주세요."
        429 -> "요청이 몰리고 있어요. 잠시 후 다시 시도해 주세요."
        502 -> "인식 결과를 확인하지 못했어요. 다시 찍거나 직접 입력해 주세요."
        503 -> "지금은 인식을 이용하기 어려워요. 잠시 후 다시 시도해 주세요."
        else -> "인식을 완료하지 못했어요. 다시 시도하거나 직접 입력해 주세요."
    }
    // A picked photo that cannot be opened is a local problem, not the network (emulator E2E, 2026-11-20).
    error is FileNotFoundException || error is SecurityException ->
        "사진을 불러올 수 없어요. 다시 고르거나 직접 입력해 주세요."
    error is IOException -> "연결을 확인하고 다시 시도해 주세요. 직접 입력도 가능해요."
    else -> "사진을 확인하지 못했어요. 다시 찍거나 직접 입력해 주세요."
}
