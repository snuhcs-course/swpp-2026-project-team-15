// Photo-led UI regressions assisted by Codex, 2026-11-19; human review pending.
package com.example.mylittlechef.ui.design

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.model.*
import com.example.mylittlechef.ui.fridge.FridgeScreen
import com.example.mylittlechef.ui.recipe.*
import com.example.mylittlechef.ui.theme.MyLittleChefTheme
import com.example.mylittlechef.viewmodel.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class PhotoUiRegressionTest {
    @get:Rule val rule = createComposeRule()
    private val recipe = Recipe(7, "두부김치",20,2,listOf(Ingredient("두부"),Ingredient("깻잎")),listOf("두부를 데쳐요","김치와 함께 담아요"),
        missing=listOf(Ingredient("깻잎")),ingredientQuantities=listOf("1모","10장"))
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
    @Test fun widePhotoCardOpensFromItsBodyAndKeepsBookmarkSeparate() {
        var opened=0; val user=UserViewModel(); val fridge=FridgeViewModel()
        rule.setContent { MyLittleChefTheme { RecipeCard(user,fridge,recipe,{opened++},{}) } }
        val image=rule.onNodeWithTag("recipe-image-7",useUnmergedTree=true).fetchSemanticsNode().boundsInRoot
        assertTrue("Photo must be landscape",image.width>image.height*1.5f)
        rule.onNodeWithText("두부김치").performClick()
        rule.runOnIdle { assertEquals(1,opened) }
        rule.onNodeWithTag("recipe-bookmark-7").performClick()
        rule.runOnIdle { assertEquals(1,opened);assertTrue(7L in user.likes) }
    }
    @Test fun detailShowsRealAmountsMissingStatusAndKeepsOriginalOnFailure() {
        val state=SelectedRevisionState(RevisionStatus.ERROR,original=recipe,problem=SelectedProblem.NETWORK,message="연결을 확인해 주세요")
        val user=UserViewModel()
        rule.setContent { MyLittleChefTheme { RecipeDetailScreen(user,recipe,{}, {},onRequestRevision={},selectedState=state) } }
        rule.onNodeWithTag("recipe-ingredient-row-깻잎",useUnmergedTree=true).performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("깻잎 10장 · 부족").assertIsDisplayed()
        rule.onNodeWithText("다시 시도").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("두부를 데쳐요",substring=true).performScrollTo().assertIsDisplayed()
    }
}
