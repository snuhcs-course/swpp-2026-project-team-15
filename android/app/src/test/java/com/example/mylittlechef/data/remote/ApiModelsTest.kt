// AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data.remote

import com.example.mylittlechef.model.Ingredient
import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Test

// JSON samples follow server/app/{vision,recipes}/schemas.py; a renamed field would turn into null here.
class ApiModelsTest {
    private val gson = Gson()

    @Test
    fun analyzeResponse_mapsCandidatesToIngredients() {
        val json = """
            {"candidates": [{"name": "다진마늘", "raw_texts": ["국산 다진마늘 500g"], "confidence": 1.0}]}
        """

        val response = gson.fromJson(json, AnalyzeResponse::class.java)

        assertEquals(listOf("국산 다진마늘 500g"), response.candidates.single().rawTexts)
        assertEquals(listOf(Ingredient("다진마늘")), response.candidates.map { it.toIngredient() })
    }
}
