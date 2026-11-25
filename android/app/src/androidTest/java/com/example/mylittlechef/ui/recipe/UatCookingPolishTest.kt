// Cooking polish and missing-ingredient confirmation tests assisted by Codex, 2026-11-24.
package com.example.mylittlechef.ui.recipe

import android.graphics.Bitmap
import android.provider.Settings
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mylittlechef.domain.*
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.ui.components.*
import com.example.mylittlechef.viewmodel.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.File

class UatCookingPolishTest {
    @get:Rule val rule=createComposeRule()
    private val dish=Dish("polish","계란밥","밥",listOf("밥"),listOf("계란"),"","",true)
    private val original=DishRecipe("polish",dish.name,videoTitle=null,videoChannel=null,servings=1,
        ingredients=listOf(RecipeIngredient("밥","1공기",Availability.OWNED),RecipeIngredient("계란","1개",Availability.UNAVAILABLE)),
        steps=listOf(RecipeStep(1,"계란을 볶아요"),RecipeStep(2,"밥을 섞어요")),tips=emptyList(),uncertain=emptyList(),captionGaps=false)
    private val revised=Revision.Revised(1,listOf(RevisedIngredient("밥","1공기"),RevisedIngredient("두부","반 모")),
        listOf(RecipeStep(1,"두부와 밥을 볶아요")),emptyList(),emptyList())
    @Composable private fun Detail(recipe:DishRecipe=original,state:ReviseUiState?=null,onRequest:()->Unit={}) {
        CompositionLocalProvider(LocalLoadingMotionOverride provides false) {MaterialTheme {
            RecipeDetailScreen(dish,false,RecipeUiState.Success(recipe),state,VideoUiState.Success(emptyList()),null,{},{},{},onRequest,{})
        }}
    }
    private fun capture(name:String) {
        val i=InstrumentationRegistry.getInstrumentation();i.uiAutomation.waitForIdle(100,3000)
        File(i.targetContext.cacheDir,name).outputStream().use {requireNotNull(i.uiAutomation.takeScreenshot()).compress(Bitmap.CompressFormat.PNG,100,it)}
    }
    @Test fun missingOriginalPromptsAndAIIsReviewedBeforeCooking() {
        var state by mutableStateOf<ReviseUiState?>(null);var requests=0
        rule.setContent {Detail(state=state,onRequest={requests++;state=ReviseUiState.Loading})}
        rule.onNodeWithTag("start-cooking").performScrollTo().performClick()
        rule.onNodeWithText("부족한 재료가 있어요").assertIsDisplayed()
        rule.onNodeWithTag("cooking-mode").assertDoesNotExist()
        rule.onNodeWithTag("cancel-missing-cooking").performClick()
        rule.runOnIdle {assertEquals(0,requests)}
        rule.onNodeWithTag("start-cooking").performScrollTo().performClick()
        capture("cooking-missing-confirmation.png")
        rule.onNodeWithTag("cooking-show-ai").performClick()
        rule.runOnIdle {assertEquals(1,requests)}
        rule.onNodeWithTag("cooking-mode").assertDoesNotExist()
        rule.runOnIdle {state=ReviseUiState.Done(revised)}
        rule.onNodeWithTag("cooking-mode").assertDoesNotExist()
        rule.onNodeWithTag("start-cooking").performScrollTo().performClick()
        rule.onNodeWithText("AI 수정본으로 조리 중").assertIsDisplayed()
        rule.onNodeWithTag("cooking-step-text").assertTextEquals("두부와 밥을 볶아요")
        rule.runOnIdle {assertEquals(1,requests)}
    }
    @Test fun missingOriginalCanBeChosenExplicitlyWithoutAI() {
        var requests=0
        rule.setContent {Detail(onRequest={requests++})}
        rule.onNodeWithTag("start-cooking").performScrollTo().performClick()
        rule.onNodeWithTag("cook-original-anyway").performClick()
        rule.onNodeWithText("원본 레시피로 조리 중").assertIsDisplayed()
        rule.onNodeWithTag("cooking-step-text").assertTextEquals("계란을 볶아요")
        rule.runOnIdle {assertEquals(0,requests)}
    }
    @Test fun completeIngredientsStartImmediatelyAndExistingAIIsReused() {
        val complete=original.copy(ingredients=original.ingredients.map {it.copy(availability=Availability.OWNED)})
        rule.setContent {Detail(recipe=complete)}
        rule.onNodeWithTag("start-cooking").performScrollTo().performClick()
        rule.onNodeWithText("부족한 재료가 있어요").assertDoesNotExist()
        rule.onNodeWithTag("cooking-mode").assertExists()
    }
    @Test fun availableAIIsSelectedWithoutASecondRequest() {
        var requests=0
        rule.setContent {Detail(state=ReviseUiState.Done(revised),onRequest={requests++})}
        rule.onNodeWithTag("start-cooking").performScrollTo().performClick()
        rule.onNodeWithTag("cooking-show-ai").performClick()
        rule.onNodeWithTag("cooking-mode").assertDoesNotExist()
        rule.onNodeWithTag("start-cooking").performScrollTo().performClick()
        rule.onNodeWithText("AI 수정본으로 조리 중").assertIsDisplayed()
        rule.runOnIdle {assertEquals(0,requests)}
    }
    @Test fun consumedIconsSupportRoundTripDragAndOnlyConfirmedItemsAreRemovedThenRestored() {
        val recipe=original.copy(ingredients=listOf("밥","계란","두부").map {RecipeIngredient(it,null,Availability.OWNED)})
        val fridge=FridgeViewModel().apply {addIngredients(listOf("밥","계란","두부","김치").map(::Ingredient))}
        rule.setContent {MaterialTheme {CookingCompletionDialog("test",recipe,fridge,{})}}
        val names=listOf("밥","계란","두부")
        names.forEach {rule.onNodeWithTag("consumed-$it").assertIsOff()}
        fun stroke() {
            val first=rule.onNodeWithTag("consumed-밥").fetchSemanticsNode().boundsInRoot.center
            val last=rule.onNodeWithTag("consumed-두부").fetchSemanticsNode().boundsInRoot.center
            val origin=rule.onNodeWithTag("consumed-choices").fetchSemanticsNode().boundsInRoot.topLeft
            rule.onNodeWithTag("consumed-choices").performTouchInput {
                down(first-origin);advanceEventTime(700);moveTo(last-origin,300);moveTo(first-origin,300);up()
            }
        }
        stroke();names.forEach {rule.onNodeWithTag("consumed-$it").assertIsOn()}
        stroke();names.forEach {rule.onNodeWithTag("consumed-$it").assertIsOff()}
        rule.runOnIdle {assertEquals(4,fridge.ingredients.size)}
        rule.onNodeWithTag("consumed-계란").performClick().assertIsOn()
        rule.onNodeWithTag("selected-icon-계란",useUnmergedTree=true).assertExists()
        capture("cooking-consumed-icons.png")
        rule.onNodeWithTag("consumed-confirm").performClick()
        rule.onNodeWithText("재료를 정리했어요").assertIsDisplayed()
        rule.runOnIdle {assertEquals(listOf("밥","두부","김치"),fridge.ingredients.map {it.name})}
        rule.onNodeWithText("실행 취소").performClick()
        rule.runOnIdle {assertEquals(listOf("밥","계란","두부","김치"),fridge.ingredients.map {it.name})}
    }
    @Test fun cardsAnimateBetweenStepsWithoutMovingNavigationButtons() {
        val run=startCookingRun(original)
        rule.setContent {MaterialTheme {CookingCards(run,{}, {})}}
        rule.onNodeWithTag("cooking-step-text").assertTextEquals("계란을 볶아요")
        val before=rule.onNodeWithTag("cooking-next").fetchSemanticsNode().boundsInRoot
        val motion=Settings.Global.getFloat(InstrumentationRegistry.getInstrumentation().targetContext.contentResolver,
            Settings.Global.ANIMATOR_DURATION_SCALE,1f)>0f
        try {
            rule.mainClock.autoAdvance=false
            rule.onNodeWithTag("cooking-next").performClick()
            rule.mainClock.advanceTimeBy(80)
            if(motion) assertTrue(rule.onAllNodesWithTag("cooking-step-card").fetchSemanticsNodes().size>=2)
            rule.mainClock.advanceTimeBy(400)
        } finally {rule.mainClock.autoAdvance=true}
        rule.onNodeWithTag("cooking-step-text").assertTextEquals("밥을 섞어요")
        assertEquals(before,rule.onNodeWithTag("cooking-next").fetchSemanticsNode().boundsInRoot)
        capture("cooking-step-card.png")
        rule.onNodeWithTag("cooking-previous").performClick()
        rule.onNodeWithTag("cooking-step-text").assertTextEquals("계란을 볶아요")
    }
}
