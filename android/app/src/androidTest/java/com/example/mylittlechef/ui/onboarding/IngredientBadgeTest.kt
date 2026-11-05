// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui.onboarding

import androidx.compose.foundation.layout.Row
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toPixelMap
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.captureToImage
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithContentDescription
import androidx.compose.ui.test.onNodeWithTag
import com.example.mylittlechef.ui.components.IngredientBadge
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

class IngredientBadgeTest {
    @get:Rule val rule = createComposeRule()

    @Test fun knownAndUnknownNamesRenderCatalogDiscsAndRemainAccessible() {
        rule.setContent {
            MaterialTheme {
                Row {
                    IngredientBadge("소금", Modifier.testTag("known"))
                    IngredientBadge("처음 보는 재료", Modifier.testTag("fallback"))
                }
            }
        }
        rule.onNodeWithContentDescription("소금").assertExists()
        rule.onNodeWithContentDescription("처음 보는 재료").assertExists()
        val known = rule.onNodeWithTag("known").captureToImage().toPixelMap()
        val fallback = rule.onNodeWithTag("fallback").captureToImage().toPixelMap()
        // Sample above the vector line art, inside the disc. Values come from the CSV / fallback contract.
        assertEquals(Color(0xFFE5EBF0), known[known.width / 2, known.height / 10])
        assertEquals(Color(0xFFE2E5E7), fallback[fallback.width / 2, fallback.height / 10])
    }
}
