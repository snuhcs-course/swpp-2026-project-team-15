// Multi-selection regressions assisted by Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui.fridge

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.data.local.FridgeRepository
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.UserViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import org.junit.Rule
import org.junit.Test
import java.io.IOException

class FridgeDeletionUiTest {
    @get:Rule val composeRule = createComposeRule()

    private fun show(vararg names: String, repository: FridgeRepository? = null) {
        val fridge = FridgeViewModel(repository)
        if (repository == null) fridge.addIngredients(names.map(::Ingredient))
        val user = UserViewModel(nickname = "테스트")
        composeRule.setContent { MaterialTheme { FridgeScreen(user, fridge, {}) } }
    }

    @Test fun longPressPreselectsThenTapTogglesAndCancelKeepsInventory() {
        show("두부", "김치")
        composeRule.onNodeWithTag("fridge-ingredient-두부").performTouchInput { longClick() }
        composeRule.onNodeWithTag("fridge-ingredient-두부").assertIsSelected()
        composeRule.onNodeWithText("1개 선택").assertIsDisplayed()
        composeRule.onNodeWithTag("confirm-ingredient-delete").assertDoesNotExist()
        composeRule.onNodeWithTag("fridge-ingredient-김치").performClick().assertIsSelected()
        composeRule.onNodeWithText("2개 선택").assertIsDisplayed()
        composeRule.onNodeWithTag("fridge-ingredient-두부").performClick().assertIsNotSelected()
        composeRule.onNodeWithText("취소").performClick()
        composeRule.onNodeWithTag("fridge-ingredient-두부").assertIsDisplayed()
        composeRule.onNodeWithTag("fridge-ingredient-김치").assertIsDisplayed()
    }

    @Test fun actionMenuEntersEmptySelectionAndSingleConfirmationDeletesSelectedNames() {
        show("마늘", "다진마늘", "두부")
        composeRule.onNodeWithTag("fridge-actions").performClick()
        composeRule.onNodeWithText("부족한 재료 추천").assertIsDisplayed()
        composeRule.onNodeWithText("냉장고 재료 추가").assertIsDisplayed()
        composeRule.onNodeWithText("냉장고 재료 삭제").performClick()
        composeRule.onNodeWithText("0개 선택").assertIsDisplayed()
        composeRule.onNodeWithTag("delete-selected-ingredients").assertIsNotEnabled()
        composeRule.onNodeWithTag("fridge-ingredient-마늘").performClick()
        composeRule.onNodeWithTag("fridge-ingredient-두부").performClick()
        composeRule.onNodeWithTag("delete-selected-ingredients").performClick()
        composeRule.onNodeWithText("선택한 재료 2개 삭제").assertIsDisplayed()
        composeRule.onNodeWithText("마늘, 두부").assertIsDisplayed()
        composeRule.onNodeWithTag("confirm-ingredient-delete").performClick()
        composeRule.onNodeWithTag("fridge-ingredient-마늘").assertDoesNotExist()
        composeRule.onNodeWithTag("fridge-ingredient-두부").assertDoesNotExist()
        composeRule.onNodeWithTag("fridge-ingredient-다진마늘").assertIsDisplayed()
        composeRule.onNodeWithTag("delete-selected-ingredients").assertDoesNotExist()
    }

    @Test fun selectAllAndCancelConfirmationPreserveSelectionUntilFinalConfirm() {
        show("두부", "김치")
        composeRule.onNodeWithTag("fridge-actions").performClick()
        composeRule.onNodeWithText("냉장고 재료 삭제").performClick()
        composeRule.onNodeWithText("전체 선택").performClick()
        composeRule.onNodeWithTag("delete-selected-ingredients").performClick()
        composeRule.onNodeWithTag("cancel-ingredient-delete").performClick()
        composeRule.onNodeWithText("2개 선택").assertIsDisplayed()
        composeRule.onNodeWithTag("delete-selected-ingredients").performClick()
        composeRule.onNodeWithTag("confirm-ingredient-delete").performClick()
        composeRule.onNodeWithText("냉장고가 비었어요").assertIsDisplayed()
        composeRule.onNodeWithTag("fridge-actions").performClick()
        composeRule.onNodeWithText("냉장고 재료 추가").assertIsEnabled()
    }

    @Test fun failedWriteKeepsInventoryAndSelectionForRetry() {
        val failedStore = object : FridgeRepository {
            override val names = MutableStateFlow(listOf("두부", "김치"))
            override suspend fun add(values: List<String>) = Unit
            override suspend fun remove(value: String) = Unit
            override suspend fun removeAll(values: Set<String>) { throw IOException("Test disk failure") }
        }
        show(repository = failedStore)
        composeRule.onNodeWithTag("fridge-ingredient-두부").performTouchInput { longClick() }
        composeRule.onNodeWithTag("delete-selected-ingredients").performClick()
        composeRule.onNodeWithTag("confirm-ingredient-delete").performClick()
        composeRule.onNodeWithText("재료를 삭제하지 못했어요. 다시 시도해 주세요.").assertIsDisplayed()
        composeRule.onNodeWithTag("fridge-ingredient-두부").assertIsSelected()
        composeRule.onNodeWithText("1개 선택").assertIsDisplayed()
        composeRule.onNodeWithTag("delete-selected-ingredients").assertIsEnabled()
    }
}
