// AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mylittlechef.data.local.UsageDataSettings
import com.example.mylittlechef.data.local.UsageDataState
import kotlinx.coroutines.launch

/** The first-run notice and the profile switch for beta-week usage data. */
class UsageDataViewModel(private val settings: UsageDataSettings) : ViewModel() {
    var state by mutableStateOf<UsageDataState?>(null)
        private set

    init {
        viewModelScope.launch { settings.state.collect { state = it } }
    }

    val showNotice get() = state?.noticeSeen == false

    fun answerNotice(send: Boolean) {
        viewModelScope.launch {
            settings.setEnabled(send)
            settings.markNoticeSeen()
        }
    }

    fun setEnabled(send: Boolean) {
        viewModelScope.launch { settings.setEnabled(send) }
    }
}
