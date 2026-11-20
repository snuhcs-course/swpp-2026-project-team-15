// AI-assisted HE follow-up regressions, 2026-11-09; manual review pending.
package com.example.mylittlechef.ui.fridge

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.ui.fridge.add.ManualAddScreen
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.IngredientCatalogViewModel
import okhttp3.MultipartBody
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class HeManualEntryUiTest {
    @get:Rule val rule = createComposeRule()
    private val api = object : IngredientSupportApi {
        override suspend fun ingredientNames() = IngredientCatalogResponse(listOf("두부", "무"))
        override suspend fun ingredientSuggestions(request: IngredientSuggestionRequest) = error("Not used")
        override suspend fun analyze(image: MultipartBody.Part) = error("Not used")
    }
    @Test fun entryFieldIsVisibleBeforeAddAndMultipleRowsCanStillBeSaved() {
        val fridge = FridgeViewModel()
        val catalog = IngredientCatalogViewModel(api)
        var saved = false
        rule.setContent { MaterialTheme { ManualAddScreen(fridge, catalog, {}, { saved = true }) } }
        rule.onAllNodes(hasSetTextAction()).assertCountEquals(1)
        rule.onNode(hasSetTextAction()).assertIsDisplayed().assertIsNotFocused()
            .performClick().assertIsFocused().performTextInput("두부")
        rule.onNodeWithText("+ 식재료 추가").performScrollTo().performClick()
        rule.onNode(hasSetTextAction()).performScrollTo().performTextInput("무")
        rule.onNodeWithText("저장").performClick()
        rule.runOnIdle {
            assertTrue(saved)
            assertEquals(listOf("두부", "무"), fridge.ingredients.map { it.name })
        }
    }
}
