// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mylittlechef.data.local.AppDataReset
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

/** Runs the "데이터 초기화" action: one request at a time, an error text when it fails. */
class DataResetViewModel(private val reset: AppDataReset) : ViewModel() {
    var isResetting by mutableStateOf(false)
        private set

    var error by mutableStateOf<String?>(null)
        private set

    fun dismissError() {
        error = null
    }

    /** [onDone] runs after the stored data is gone, never when the reset failed. */
    fun resetAll(onDone: () -> Unit) {
        if (isResetting) return
        isResetting = true
        error = null
        viewModelScope.launch {
            try {
                reset.resetAll()
                onDone()
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                error = "초기화하지 못했어요. 다시 시도해 주세요."
            } finally {
                isResetting = false
            }
        }
    }
}
