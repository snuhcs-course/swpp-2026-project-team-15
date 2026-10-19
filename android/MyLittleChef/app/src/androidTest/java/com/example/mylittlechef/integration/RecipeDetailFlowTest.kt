package com.example.mylittlechef.integration

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.model.*
import com.example.mylittlechef.ui.recipe.IntegratedRecipeDetail
import org.junit.Rule
import org.junit.Test

/** US05: the original remains available before and after an explicit AI view toggle. */
class RecipeDetailFlowTest {
    @get:Rule val compose = createComposeRule()
    private val original = RecipeText("Original dish", "2 servings", listOf("Egg 2"), listOf("Original step"))

    @Test fun revisedViewIsExplicitAndCanReturnToOriginal() {
        val suggestion = original.copy(name = "Suggested dish", steps = listOf("Suggested step"))
        compose.setContent { IntegratedRecipeDetail(Recipe(20, "Original dish", 10, 2,
            emptyList(), emptyList(), source = original,
            revision = RecipeRevisionInfo("revised", "MOCK ONLY", suggestion))) }
        compose.onNodeWithTag("recipe-version").assertTextEquals("원본 레시피")
        compose.onNodeWithTag("recipe-version-toggle").performClick()
        compose.onNodeWithTag("recipe-version").assertTextEquals("AI 수정 제안")
        compose.onNodeWithText("Suggested dish").assertIsDisplayed()
        compose.onNodeWithTag("recipe-version-toggle").performClick()
        compose.onNodeWithText("Original dish").assertIsDisplayed()
    }

    @Test fun refusedRevisionKeepsOriginalAndExplainsStatus() {
        compose.setContent { IntegratedRecipeDetail(Recipe(20, "Original dish", 10, 2,
            emptyList(), emptyList(), source = original,
            revision = RecipeRevisionInfo("refused", "MOCK ONLY"))) }
        compose.onNodeWithTag("revision-status").assertTextEquals("AI 수정 거절: MOCK ONLY")
        compose.onNodeWithTag("recipe-version-toggle").assertDoesNotExist()
        compose.onNodeWithText("Original dish").assertIsDisplayed()
    }
}
