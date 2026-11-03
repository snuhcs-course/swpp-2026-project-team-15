package com.example.mylittlechef.ui.fridge

import android.graphics.Bitmap
import androidx.compose.material3.MaterialTheme
import androidx.test.platform.app.InstrumentationRegistry
import java.io.File
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertIsEnabled
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.longClick
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTouchInput
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

    private fun capture(name: String) {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        composeRule.waitForIdle()
        InstrumentationRegistry.getInstrumentation().uiAutomation.waitForIdle(100, 3_000)
        val bitmap = requireNotNull(InstrumentationRegistry.getInstrumentation().uiAutomation.takeScreenshot())
        File(context.cacheDir, name).outputStream().use {
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)
        }
    }

    private fun show(vararg names: String, repository: FridgeRepository? = null) {
        val fridge = FridgeViewModel(repository)
        if (repository == null) fridge.addIngredients(names.map(::Ingredient))
        val user = UserViewModel(nickname = "테스트")
        composeRule.setContent {
            MaterialTheme {
                FridgeScreen(user, fridge, {})
            }
        }
    }

    @Test fun longPressThenCancelKeepsBothIngredients() {
        show("두부", "김치")
        composeRule.onNodeWithTag("fridge-ingredient-두부").performTouchInput { longClick() }
        composeRule.onNodeWithText("두부 삭제").assertIsDisplayed()
        capture("iter3-fridge-delete-dialog.png")
        composeRule.onNodeWithText("취소").performClick()
        composeRule.onNodeWithTag("fridge-ingredient-두부").assertIsDisplayed()
        composeRule.onNodeWithTag("fridge-ingredient-김치").assertIsDisplayed()
        capture("iter3-fridge-default.png")
    }

    @Test fun managementControlDeletesOnlyTheChosenName() {
        show("마늘", "다진마늘")
        composeRule.onNodeWithText("관리").performClick()
        capture("iter3-fridge-manage.png")
        composeRule.onNodeWithTag("fridge-delete-마늘").performClick()
        composeRule.onNodeWithTag("confirm-ingredient-delete").performClick()
        composeRule.onNodeWithTag("fridge-ingredient-마늘").assertDoesNotExist()
        composeRule.onNodeWithTag("fridge-ingredient-다진마늘").assertIsDisplayed()
    }

    @Test fun deletingLastIngredientKeepsTheAddActionAvailable() {
        show("두부")
        composeRule.onNodeWithTag("fridge-ingredient-두부").performTouchInput { longClick() }
        composeRule.onNodeWithTag("confirm-ingredient-delete").performClick()
        composeRule.onNodeWithTag("fridge-ingredient-두부").assertDoesNotExist()
        composeRule.onNodeWithText("냉장고가 비었어요").assertIsDisplayed()
        composeRule.onNodeWithText("재료 추가").assertIsEnabled()
    }

    @Test fun failedWriteShowsFeedbackAndKeepsTheIngredient() {
        val failedStore = object : FridgeRepository {
            override val names = MutableStateFlow(listOf("두부"))
            override suspend fun add(values: List<String>) = Unit
            override suspend fun remove(value: String) { throw IOException("Test disk failure") }
        }
        show(repository = failedStore)
        composeRule.onNodeWithTag("fridge-ingredient-두부").performTouchInput { longClick() }
        composeRule.onNodeWithTag("confirm-ingredient-delete").performClick()
        composeRule.onNodeWithText("재료를 삭제하지 못했어요. 다시 시도해 주세요.").assertIsDisplayed()
        composeRule.onNodeWithTag("fridge-ingredient-두부").assertIsDisplayed()
    }
}
