// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toPixelMap
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.ui.fridge.components.EditableIngredientList
import com.example.mylittlechef.ui.fridge.components.IngredientEditorState
import com.example.mylittlechef.ui.profile.ProfileScreen
import com.example.mylittlechef.ui.profile.EditNicknameScreen
import com.example.mylittlechef.ui.theme.MyLittleChefTheme
import com.example.mylittlechef.ui.theme.AppearanceSettings
import com.example.mylittlechef.ui.theme.LocalAppearanceSettings
import com.example.mylittlechef.domain.ThemeMode
import com.example.mylittlechef.ui.recipe.RecipeIngredients
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.viewmodel.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class UiPolishRegressionTest {
    @get:Rule val rule=createComposeRule()

    @Test fun exactTypedIngredientStillOffersASelectableCanonicalMatch() {
        val editor=IngredientEditorState().apply { startAdd() }
        rule.setContent { MaterialTheme { EditableIngredientList(editor,listOf("무","무순","무청")) } }
        rule.onNode(hasSetTextAction()).performTextInput("무")
        rule.onNode(hasText("무") and hasClickAction() and !hasSetTextAction()).assertIsDisplayed().performClick()
        rule.runOnIdle { assertNull(editor.editingIndex); assertEquals(listOf("무"),editor.ingredients.map { it.name }) }
    }

    @Test fun profileUsesDarkSurfaceInsteadOfHardcodedWhite() {
        val user=UserViewModel(nickname="테마 확인"); val fridge=FridgeViewModel()
        var expected=Color.Unspecified
        rule.setContent { MyLittleChefTheme(darkTheme=true,dynamicColor=false) {
            expected=MaterialTheme.colorScheme.background
            Box(Modifier.fillMaxSize().testTag("profile-root")) { ProfileScreen(user,fridge,{},{},{},{}) }
        } }
        val actual=rule.onNodeWithTag("profile-root").captureToImage().toPixelMap()[2,2]
        assertEquals(expected,actual)
    }

    @Test fun profileModePickerSwitchesBothWaysAndCanRestoreSystem() {
        val user=UserViewModel(nickname="테마 확인"); val fridge=FridgeViewModel()
        var mode by mutableStateOf(ThemeMode.SYSTEM)
        var expected=Color.Unspecified
        rule.setContent {
            CompositionLocalProvider(LocalAppearanceSettings provides AppearanceSettings(mode,onSelect={mode=it})) {
                MyLittleChefTheme(darkTheme=mode.isDark(false)) {
                    expected=MaterialTheme.colorScheme.background
                    Box(Modifier.fillMaxSize().testTag("profile-root")) { ProfileScreen(user,fridge,{},{},{},{}) }
                }
            }
        }
        rule.onNodeWithContentDescription("화면 모드 설정: 시스템 설정").performClick()
        rule.onNodeWithText("다크 모드").performClick()
        rule.onNodeWithContentDescription("화면 모드 설정: 다크 모드").assertExists()
        assertEquals(expected,rule.onNodeWithTag("profile-root").captureToImage().toPixelMap()[2,2])
        rule.onNodeWithContentDescription("화면 모드 설정: 다크 모드").performClick()
        rule.onNodeWithText("라이트 모드").performClick()
        rule.onNodeWithContentDescription("화면 모드 설정: 라이트 모드").performClick()
        rule.onNodeWithText("시스템 설정").performClick()
        rule.runOnIdle { assertEquals(ThemeMode.SYSTEM,mode) }
    }

    @Test fun recipeIngredientsReuseCatalogIconsAndKeepMissingQuantityText() {
        rule.setContent { MyLittleChefTheme(darkTheme=true) {
            RecipeIngredients(listOf(Ingredient("소금"),Ingredient("마늘")),listOf("1작은술","2쪽"),setOf("소금"))
        } }
        rule.onNodeWithContentDescription("소금").assertIsDisplayed()
        rule.onNodeWithContentDescription("마늘").assertIsDisplayed()
        rule.onNodeWithText("소금 1작은술 · 부족").assertIsDisplayed()
        rule.onNodeWithText("마늘 2쪽").assertIsDisplayed()
    }

    @Test fun darkProfileSaveLabelHasReadableContrast() {
        val user=UserViewModel(nickname="테스트")
        rule.setContent { MyLittleChefTheme(darkTheme=true) { EditNicknameScreen(user,{},{}) } }
        val button=rule.onNodeWithText("저장")
        val layouts=mutableListOf<TextLayoutResult>()
        button.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { action -> action(layouts) }
        val foreground=layouts.single().layoutInput.style.color
        val pixels=button.captureToImage().toPixelMap()
        val background=pixels[pixels.width/2,5]
        val ratio=(maxOf(foreground.luminance(),background.luminance())+.05f)/
            (minOf(foreground.luminance(),background.luminance())+.05f)
        assertTrue("Save label contrast $ratio must be >=4.5",ratio>=4.5f)
    }
}
