// AI-assisted HE UI regressions, 2026-11-09; manual review pending.
package com.example.mylittlechef.ui.fridge

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.ui.fridge.components.EditableIngredientList
import com.example.mylittlechef.ui.fridge.components.IngredientEditorState
import com.example.mylittlechef.ui.help.UsageGuideDialog
import com.example.mylittlechef.ui.profile.ProfileScreen
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.UserViewModel
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class HeEntryAndUndoUiTest {
    @get:Rule val rule = createComposeRule()

    @Test fun darkLargeTextKeepsPrimaryActionsReachable() {
        val user = UserViewModel(nickname = "테스트")
        val fridge = FridgeViewModel()
        rule.setContent {
            androidx.compose.runtime.CompositionLocalProvider(
                androidx.compose.ui.platform.LocalDensity provides androidx.compose.ui.unit.Density(
                    androidx.compose.ui.platform.LocalDensity.current.density, 1.7f)
            ) {
                com.example.mylittlechef.ui.theme.MyLittleChefTheme(darkTheme = true, dynamicColor = false) {
                    FridgeScreen(user, fridge, {})
                }
            }
        }
        rule.onNodeWithTag("fridge-manual-add").assertIsDisplayed().assertHasClickAction()
        rule.onNodeWithTag("fridge-photo-add").assertIsDisplayed().assertHasClickAction()
        rule.onNodeWithTag("ingredient-suggestions").assertIsDisplayed()
    }

    @Test fun manualAndPhotoActionsAreVisibleAndInvokeDifferentCallbacks() {
        var manual = 0
        var photos = 0
        val fridge = FridgeViewModel()
        val user = UserViewModel(nickname = "테스트")
        rule.setContent { MaterialTheme {
            FridgeScreen(user, fridge,
                onAddIngredientClick = { photos++ }, onManualAddClick = { manual++ })
        } }
        rule.onNodeWithTag("fridge-manual-add").assertIsDisplayed().performClick()
        rule.onNodeWithTag("fridge-photo-add").assertIsDisplayed().performClick()
        rule.onNodeWithTag("manual-action-icon", useUnmergedTree = true).assertIsDisplayed()
        rule.onNodeWithTag("photo-action-icon", useUnmergedTree = true).assertIsDisplayed()
        rule.onNodeWithText("추가 재료 추천").assertIsDisplayed()
        rule.onNodeWithTag("fridge-actions").assertDoesNotExist()
        rule.runOnIdle { assertEquals(1, manual); assertEquals(1, photos) }
    }

    @Test fun confirmedDeletionCanBeUndoneWithoutLosingNewIngredients() {
        val fridge = FridgeViewModel().apply { addIngredients(listOf("두부", "김치").map(::Ingredient)) }
        val user = UserViewModel(nickname = "테스트")
        rule.setContent { MaterialTheme { FridgeScreen(user, fridge, {}) } }
        rule.onNodeWithTag("manage-fridge").performClick()
        rule.onNodeWithTag("fridge-ingredient-두부").performClick()
        rule.onNodeWithTag("delete-selected-ingredients").performClick()
        rule.onNodeWithTag("confirm-ingredient-delete").performClick()
        rule.onNodeWithTag("fridge-ingredient-두부").assertDoesNotExist()
        rule.runOnIdle { fridge.addIngredients(listOf(Ingredient("계란"))) }
        rule.onNodeWithTag("undo-fridge-removal").performClick()
        rule.onNodeWithTag("fridge-ingredient-두부").assertIsDisplayed()
        rule.onNodeWithTag("fridge-ingredient-계란").assertIsDisplayed()
        rule.onNodeWithTag("fridge-undo").assertDoesNotExist()
    }

    @Test fun candidateUndoKeepsAnotherRowsEditedName() {
        val editor = IngredientEditorState(listOf("두부", "김치").map(::Ingredient))
        rule.setContent { MaterialTheme { EditableIngredientList(editor) } }
        rule.runOnIdle { editor.remove(0); editor.rename(0, "배추김치") }
        rule.onNodeWithTag("undo-candidate-removal").performClick()
        rule.onNodeWithText("두부").assertIsDisplayed()
        rule.onNodeWithText("배추김치").assertIsDisplayed()
    }

    @Test fun profileCanReopenVisualHelpAndCloseIt() {
        val user = UserViewModel(nickname = "테스트")
        val fridge = FridgeViewModel()
        rule.setContent { MaterialTheme { ProfileScreen(user, fridge, {}, {}, {}, {}) } }
        rule.onNodeWithText("사용 안내").performScrollTo()
        // The entire help row is an accessible action, not just its trailing chevron.
        rule.onNodeWithText("사용 안내").performClick()
        rule.onNodeWithTag("usage-guide").assertIsDisplayed()
        rule.onNodeWithText("1. 재료 추가").assertIsDisplayed()
        rule.onNodeWithTag("close-usage-guide").performClick()
        rule.onNodeWithTag("usage-guide").assertDoesNotExist()
    }

    @Test fun visualGuideFitsLargeTextByScrolling() {
        rule.setContent {
            androidx.compose.runtime.CompositionLocalProvider(
                androidx.compose.ui.platform.LocalDensity provides androidx.compose.ui.unit.Density(1f, 1.7f)
            ) { MaterialTheme { UsageGuideDialog(onClose = {}) } }
        }
        rule.onNodeWithTag("close-usage-guide").assertIsDisplayed()
        rule.onNodeWithText("3. AI 제안").performScrollTo().assertIsDisplayed()
    }
}
