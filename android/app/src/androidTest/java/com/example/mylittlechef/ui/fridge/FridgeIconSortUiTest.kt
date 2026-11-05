// AI-assisted with Codex, 2026-11-02; human review pending.
package com.example.mylittlechef.ui.fridge

import android.graphics.Bitmap
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.UserViewModel
import com.example.mylittlechef.data.local.IngredientPresentationProvider
import java.io.File
import org.junit.Assert.assertTrue
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Rule
import org.junit.Test

class FridgeIconSortUiTest {
    @get:Rule val rule = createComposeRule()

    private fun show(vararg names: String) {
        val fridge = FridgeViewModel().apply { addIngredients(names.map(::Ingredient)) }
        val user = UserViewModel(nickname = "테스트")
        rule.setContent { MaterialTheme { FridgeScreen(user, fridge, {}) } }
    }

    private fun capture(name: String) {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        instrumentation.uiAutomation.waitForIdle(100, 3000)
        val bitmap = requireNotNull(instrumentation.uiAutomation.takeScreenshot())
        File(instrumentation.targetContext.cacheDir, name).outputStream().use {
            bitmap.compress(Bitmap.CompressFormat.PNG, 100, it)
        }
    }

    @Test fun switchesBetweenCategoryAndAlphabeticalWithoutChangingInventory() {
        show("김치", "마늘", "다진마늘", "계란")
        rule.onNodeWithTag("fridge-sort-trigger").assertTextContains("정렬: 분류순 ⌄")
        rule.onNodeWithTag("fridge-category-vegetables").assertIsDisplayed()
        rule.onNodeWithTag("ingredient-icon-마늘", useUnmergedTree = true).assertIsDisplayed()
        capture("iter3-fridge-icons-category.png")
        rule.onNodeWithTag("fridge-sort-trigger").performClick()
        rule.onNodeWithTag("fridge-sort-ALPHABETICAL").performClick()
        rule.onNodeWithTag("fridge-sort-trigger").assertTextContains("정렬: 가나다순 ⌄")
        rule.onNodeWithTag("fridge-category-vegetables").assertDoesNotExist()
        val orderedNames = listOf("계란", "김치", "다진마늘", "마늘")
        val x = orderedNames.map {
            rule.onNodeWithTag("fridge-ingredient-$it").assertIsDisplayed()
                .fetchSemanticsNode().boundsInRoot.left
        }
        assertTrue(x.zipWithNext().all { (a,b) -> a < b })
        capture("iter3-fridge-icons-alphabetical.png")
        rule.onNodeWithTag("fridge-sort-trigger").performClick()
        rule.onNodeWithTag("fridge-sort-ADDED").performClick()
        rule.onNodeWithTag("fridge-sort-trigger").assertTextContains("정렬: 추가순 ⌄")
        val addedX = listOf("김치", "마늘", "다진마늘", "계란").map {
            rule.onNodeWithTag("fridge-ingredient-$it").fetchSemanticsNode().boundsInRoot.left
        }
        assertTrue(addedX.zipWithNext().all { (a,b) -> a < b })
        rule.onNodeWithTag("fridge-sort-trigger").performClick()
        rule.onNodeWithTag("fridge-sort-CATEGORY").performClick()
        rule.onNodeWithTag("fridge-category-vegetables").assertIsDisplayed()
    }

    @Test fun deletingAfterSortingKeepsOtherNameWithTheSameIcon() {
        show("마늘", "다진마늘")
        rule.onNodeWithTag("fridge-sort-trigger").performClick()
        rule.onNodeWithTag("fridge-sort-ALPHABETICAL").performClick()
        rule.onNodeWithTag("fridge-actions").performClick()
        rule.onNodeWithText("냉장고 재료 삭제").performClick()
        rule.onNodeWithTag("fridge-ingredient-마늘").performClick()
        rule.onNodeWithTag("delete-selected-ingredients").performClick()
        rule.onNodeWithTag("confirm-ingredient-delete").performClick()
        rule.onNodeWithTag("fridge-ingredient-마늘").assertDoesNotExist()
        rule.onNodeWithTag("fridge-ingredient-다진마늘").assertIsDisplayed()
    }

    @Test fun unknownIngredientStillShowsAnIconAndCanBeDeleted() {
        show("처음보는재료")
        rule.onNodeWithTag("fridge-category-other").assertIsDisplayed()
        rule.onNodeWithTag("ingredient-icon-처음보는재료", useUnmergedTree = true).assertIsDisplayed()
        rule.onNodeWithTag("fridge-ingredient-처음보는재료").performTouchInput { longClick() }
        rule.onNodeWithText("취소").performClick()
        rule.onNodeWithTag("fridge-ingredient-처음보는재료").assertIsDisplayed()
        rule.onNodeWithTag("fridge-ingredient-처음보는재료").performTouchInput { longClick() }
        rule.onNodeWithTag("delete-selected-ingredients").performClick()
        rule.onNodeWithTag("confirm-ingredient-delete").performClick()
        rule.onNodeWithTag("fridge-ingredient-처음보는재료").assertDoesNotExist()
        rule.onNodeWithText("냉장고가 비었어요").assertIsDisplayed()
    }

    @Test fun packagedCatalogContainsAllMappingsAndDistinctSeasoningColors() {
        val catalog = IngredientPresentationProvider.get(InstrumentationRegistry.getInstrumentation().targetContext)
        assertEquals(560, catalog.size)
        assertEquals("seasoning", catalog.appearanceFor("소금").iconKey)
        assertEquals("seasoning", catalog.appearanceFor("고춧가루").iconKey)
        assertNotEquals(catalog.appearanceFor("소금").backgroundColor, catalog.appearanceFor("고춧가루").backgroundColor)
    }
}
