// AI-assisted with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
package com.example.mylittlechef.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PantryPresetsTest {
    @Test fun pantryChoicesAreTwentyDistinctCommonItems() {
        val all = Preset.pantrySeasonings + Preset.pantryBasics
        assertEquals(20, all.size)
        assertEquals(all.size, all.distinct().size)
        assertTrue(listOf("식용유", "소금", "설탕", "간장").all { it in Preset.pantrySeasonings })
        assertTrue(listOf("밥", "계란", "양파", "대파").all { it in Preset.pantryBasics })
    }
}
