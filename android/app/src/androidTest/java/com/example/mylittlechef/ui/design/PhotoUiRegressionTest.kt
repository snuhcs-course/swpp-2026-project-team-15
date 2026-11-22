// Photo-led UI regressions assisted by Codex, 2026-11-19; human review pending.
// Modified with Claude Code (Opus 5.5), 2026-11-20: recipe-card cases moved to ui/recipe.
package com.example.mylittlechef.ui.design

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.model.*
import com.example.mylittlechef.ui.fridge.FridgeScreen
import com.example.mylittlechef.ui.theme.MyLittleChefTheme
import com.example.mylittlechef.viewmodel.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class PhotoUiRegressionTest {
    @get:Rule val rule = createComposeRule()
    @Test fun fridgeKeepsDirectActionsAndMultiSelectUndoInNewLayout() {
        val fridge=FridgeViewModel().apply { addIngredients(listOf(Ingredient("두부"),Ingredient("계란"))) }
        val user=UserViewModel()
        rule.setContent { MyLittleChefTheme { FridgeScreen(user,fridge,{}) } }
        rule.onNodeWithText("내 냉장고").assertIsDisplayed()
        rule.onNodeWithTag("fridge-photo-add").assertIsDisplayed()
        rule.onNodeWithTag("fridge-manual-add").assertIsDisplayed()
        rule.onNodeWithTag("manage-fridge").performClick()
        rule.onNodeWithTag("fridge-ingredient-두부").performClick()
        rule.onNodeWithTag("fridge-ingredient-계란").performClick()
        rule.onNodeWithTag("delete-selected-ingredients").performClick()
        rule.onNodeWithTag("confirm-ingredient-delete").performClick()
        rule.onNodeWithTag("undo-fridge-removal").performClick()
        rule.onNodeWithTag("fridge-ingredient-두부").assertIsDisplayed()
        rule.onNodeWithTag("fridge-ingredient-계란").assertIsDisplayed()
    }
    // The photo-card and bookmark checks of #24 now live in ui/recipe/RecipeCardInteractionTest on the
    // YouTube-based dishes (2026-11-20); the old Recipe model they targeted is gone.
}
