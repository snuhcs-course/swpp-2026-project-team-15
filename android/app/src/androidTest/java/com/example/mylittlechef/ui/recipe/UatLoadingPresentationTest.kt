// Centered loading and concise changes verified with Codex, 2026-11-24; human review pending.
package com.example.mylittlechef.ui.recipe

import android.graphics.Bitmap
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.SemanticsActions
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.text.TextLayoutResult
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.domain.*
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.ui.components.*
import com.example.mylittlechef.viewmodel.*
import kotlinx.coroutines.CompletableDeferred
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.File

class UatLoadingPresentationTest {
    @get:Rule val rule = createComposeRule()

    private fun layout(tag: String): TextLayoutResult {
        val results = mutableListOf<TextLayoutResult>()
        rule.onNodeWithTag(tag).performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(results) }
        return results.single()
    }
    private fun capture(name: String) {
        val i = InstrumentationRegistry.getInstrumentation()
        i.uiAutomation.waitForIdle(100, 3000)
        File(i.targetContext.cacheDir, name).outputStream().use {
            requireNotNull(i.uiAutomation.takeScreenshot()).compress(Bitmap.CompressFormat.PNG, 100, it)
        }
    }

    @Test fun actualRecipeListLoadingIsCenteredInTheContentArea() {
        val gate = CompletableDeferred<Unit>()
        var requests = 0
        val api = object : DishApi {
            override suspend fun dishes() = DishCatalogResponse(emptyList(), 0)
            override suspend fun videos(request: DishVideosRequest) = DishVideosResponse(emptyList())
            override suspend fun suggest(request: DishSuggestRequest): DishSuggestResponse {
                requests++; gate.await()
                return DishSuggestResponse("mock", emptyList())
            }
        }
        val dishes = DishViewModel(api, debounceMillis=0)
        val fridge = FridgeViewModel().apply { addIngredients(listOf(Ingredient("밥"))) }
        rule.setContent {
            CompositionLocalProvider(LocalLoadingMotionOverride provides false) {
                MaterialTheme { Box(Modifier.safeDrawingPadding()) { RecipeScreen(fridge,dishes,{}) } }
            }
        }
        try {
            rule.waitUntil { requests == 1 }
            val area = rule.onNodeWithTag("recipe-list-content").fetchSemanticsNode().boundsInRoot
            val loading = rule.onNodeWithTag("recipe-list-progress").assertIsDisplayed().fetchSemanticsNode().boundsInRoot
            assertEquals(area.center.x,loading.center.x,1f)
            assertEquals(area.center.y,loading.center.y,1f)
            val text = rule.onNodeWithText(LoadingTask.DISHES.message,useUnmergedTree=true)
            val results = mutableListOf<TextLayoutResult>()
            text.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(results) }
            assertEquals(TextAlign.Center,results.single().layoutInput.style.textAlign)
            capture("centered-recipe-loading.png")
            rule.runOnIdle { assertEquals(1,requests) }
        } finally { gate.complete(Unit) }
    }

    @Test fun allLoadingTasksKeepIconAndTextCenteredAndReadable() {
        var task by mutableStateOf(LoadingTask.RECIPE)
        rule.setContent {
            CompositionLocalProvider(LocalLoadingMotionOverride provides false) {
                MaterialTheme {
                    Box(Modifier.fillMaxWidth().height(300.dp).testTag("loading-area"),contentAlignment=Alignment.Center) {
                        IngredientLoading(task,Modifier.testTag("loading-block"))
                    }
                }
            }
        }
        LoadingTask.entries.forEach { value ->
            rule.runOnIdle { task=value }
            val area = rule.onNodeWithTag("loading-area").fetchSemanticsNode().boundsInRoot
            val block = rule.onNodeWithTag("loading-block").fetchSemanticsNode().boundsInRoot
            val icon = rule.onNodeWithTag("loading-icon-0",useUnmergedTree=true).fetchSemanticsNode().boundsInRoot
            val text = rule.onNodeWithText(value.message,useUnmergedTree=true)
            val textBounds = text.assertIsDisplayed().fetchSemanticsNode().boundsInRoot
            assertEquals(area.center.y,block.center.y,1f)
            assertEquals(block.center.x,icon.center.x,1f)
            assertEquals(block.center.x,textBounds.center.x,1f)
            val results = mutableListOf<TextLayoutResult>()
            text.performSemanticsAction(SemanticsActions.GetTextLayoutResult) { it(results) }
            assertEquals(TextAlign.Center,results.single().layoutInput.style.textAlign)
        }
    }

    @Test fun longChangeReasonShowsTwoLinesAndExpandsWithoutAnyAIRequest() {
        val dish = Dish("layout-demo","검증용 계란밥","밥",listOf("밥"),listOf("계란"),"","",true)
        val original = DishRecipe("layout-demo",dish.name,videoTitle=null,videoChannel=null,servings=1,
            ingredients=listOf(RecipeIngredient("계란","1개",Availability.UNAVAILABLE)),
            steps=listOf(RecipeStep(1,"계란을 넣고 볶아요")),tips=emptyList(),uncertain=emptyList(),captionGaps=false)
        val reason = "계란이 없어 두부로 바꾸고 물기를 뺀 뒤 볶도록 조리 순서를 조정했어요. ".repeat(8)
        val revised = Revision.Revised(1,listOf(RevisedIngredient("두부","반 모")),
            listOf(RecipeStep(1,"두부의 물기를 빼고 볶아요")),emptyList(),
            listOf(RecipeChange(reason,listOf(1),listOf(1),ChangeKind.SUBSTITUTION)))
        var requests = 0
        rule.setContent { MaterialTheme {
            RecipeDetailScreen(dish,false,RecipeUiState.Success(original),ReviseUiState.Done(revised),
                VideoUiState.Success(emptyList()),null,{},{},{},{requests++},{})
        } }
        rule.onNodeWithTag("revision-toggle").performScrollTo().performClick()
        rule.onNodeWithTag("revision-changes-toggle").performScrollTo().performClick()
        rule.onNodeWithTag("recipe-change").performScrollTo().assertIsDisplayed()
        assertEquals(2,layout("recipe-change").lineCount)
        assertTrue(layout("recipe-change").hasVisualOverflow)
        rule.onNodeWithText("재료: 계란").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("조리 단계: 1").performScrollTo().assertIsDisplayed()
        capture("concise-recipe-changes.png")
        rule.onNodeWithText("자세히").performScrollTo().performClick()
        assertTrue(layout("recipe-change").lineCount > 2)
        assertFalse(layout("recipe-change").hasVisualOverflow)
        rule.onNodeWithText("간단히").performScrollTo().performClick()
        assertEquals(2,layout("recipe-change").lineCount)
        rule.runOnIdle { assertEquals(0,requests) }
    }
}
