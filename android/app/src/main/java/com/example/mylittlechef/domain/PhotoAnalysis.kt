// AI-assisted HE review state, 2026-11-09; manual review pending.
package com.example.mylittlechef.domain

import com.example.mylittlechef.model.Ingredient

enum class RecognitionMode { MOCK, LIVE, UNKNOWN }

data class PhotoAnalysis(
    val candidates: List<Ingredient>,
    val imageUris: List<String>,
    val mode: RecognitionMode = RecognitionMode.UNKNOWN
)

sealed interface PhotoAnalysisState {
    data object Loading : PhotoAnalysisState
    data class Ready(val result: PhotoAnalysis) : PhotoAnalysisState
    data class Empty(val result: PhotoAnalysis) : PhotoAnalysisState
    data class Failed(val message: String) : PhotoAnalysisState
    data object Cancelled : PhotoAnalysisState
}
