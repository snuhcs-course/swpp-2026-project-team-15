// UAT selection footer layout assisted by Codex, 2026-11-24; human review pending.
package com.example.mylittlechef.ui

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.navigation.MainScreen
import com.example.mylittlechef.ui.theme.MyLittleChefTheme
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.UserViewModel
import androidx.test.platform.app.InstrumentationRegistry
import android.graphics.Bitmap
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test

class UatFridgeSelectionLayoutTest {
    @get:Rule val rule = createComposeRule()

    private fun capture(name: String) {
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        instrumentation.uiAutomation.waitForIdle(100, 3000)
        File(instrumentation.targetContext.cacheDir, name).outputStream().use {
            requireNotNull(instrumentation.uiAutomation.takeScreenshot()).compress(Bitmap.CompressFormat.PNG, 100, it)
        }
    }

    @Test fun longPressKeepsTilesInPlaceAndShowsSelectionControlsBelowThem() {
        val fridge = FridgeViewModel().apply { addIngredients(listOf("두부", "마늘", "계란").map(::Ingredient)) }
        val user = UserViewModel()
        rule.setContent { MyLittleChefTheme { MainScreen(user, fridge, {}, {}, {}, {}) } }
        val names = listOf("두부", "마늘", "계란")
        fun bounds(name: String) = rule.onNodeWithTag("fridge-ingredient-$name").fetchSemanticsNode().boundsInRoot
        val before = names.associateWith(::bounds)
        capture("selection-footer-before.png")
        rule.onNodeWithTag("fridge-ingredient-두부").performTouchInput { longClick() }
        rule.onNodeWithTag("fridge-ingredient-두부").assertIsSelected()
        names.forEach { assertEquals(before.getValue(it), bounds(it)) }
        val footer = rule.onNodeWithTag("fridge-selection-summary").assertIsDisplayed().fetchSemanticsNode().boundsInRoot
        assertTrue(footer.top >= names.maxOf { bounds(it).bottom })
        capture("selection-footer-after.png")
        File(InstrumentationRegistry.getInstrumentation().targetContext.cacheDir, "selection-footer-coordinates.txt")
            .writeText(names.joinToString("\n") { "$it: before=${before.getValue(it)}; after=${bounds(it)}" })
        rule.onNodeWithText("전체 선택").performClick()
        names.forEach {
            rule.onNodeWithTag("fridge-ingredient-$it").assertIsSelected()
            assertEquals(before.getValue(it), bounds(it))
        }
        rule.onNodeWithText("취소").performClick()
        names.forEach { assertEquals(before.getValue(it), bounds(it)) }
    }
}
