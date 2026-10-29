// AI-assisted with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
package com.example.mylittlechef.ui.onboarding

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

class OnboardingPantryTest {
    @get:Rule val composeRule = createComposeRule()

    @Test fun selectedPantryItemsAreReturnedOnNext() {
        var selected by mutableStateOf<List<String>>(emptyList())
        var advanced = false
        composeRule.setContent {
            OnboardingPantry(
                selected = selected,
                onSelectedChange = { selected = it },
                onNext = { advanced = true },
                onBack = {}
            )
        }
        composeRule.onNodeWithText("소금").performClick()
        composeRule.onNodeWithText("설탕").performClick()
        composeRule.runOnIdle { assertEquals(listOf("소금", "설탕"), selected) }
        composeRule.onNodeWithText("다음").performClick()
        composeRule.runOnIdle { assertEquals(true, advanced) }
    }

    @Test fun pantrySelectionCanBeUnchecked() {
        var selected by mutableStateOf(listOf("소금"))
        composeRule.setContent {
            OnboardingPantry(
                selected = selected,
                onSelectedChange = { selected = it },
                onNext = {},
                onBack = {}
            )
        }
        composeRule.onNodeWithText("소금").performClick()
        composeRule.runOnIdle { assertEquals(emptyList<String>(), selected) }
    }
}
