// UAT stage 3 integrated UI tests assisted by Codex, 2026-11-24.
package com.example.mylittlechef.ui.recipe
import android.content.ClipData
import android.content.ClipboardManager
import android.os.SystemClock
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.lifecycle.*
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mylittlechef.domain.*
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.model.Ingredient
import kotlinx.coroutines.CompletableDeferred
import com.example.mylittlechef.viewmodel.*
import com.example.mylittlechef.ui.components.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class UatRecipeToolsTest {
 @get:Rule val rule=createComposeRule()
 private val dish=Dish("demo","계란밥","밥",listOf("밥"),listOf("계란"),"","",true)
 private val recipe=DishRecipe("demo","계란밥",videoTitle=null,videoChannel=null,servings=1,
  ingredients=listOf(RecipeIngredient("밥","1/2 공기",Availability.OWNED),RecipeIngredient("계란","1개",Availability.UNAVAILABLE),RecipeIngredient("소금","적당량",Availability.ASSUMED)),
  steps=listOf(RecipeStep(1,"계란을 볶아요"),RecipeStep(2,"밥을 섞어요")),tips=emptyList(),uncertain=emptyList(),captionGaps=false)
 private val revision=Revision.Revised(1,listOf(RevisedIngredient("밥","1/2 공기"),RevisedIngredient("두부",null)),
  listOf(RecipeStep(1,"두부와 밥을 볶아요")),emptyList(),listOf(RecipeChange("계란 대신 두부를 사용해요",listOf(2),listOf(1),ChangeKind.SUBSTITUTION)))
 @Composable private fun Detail(onRequest:()->Unit={}) {
  RecipeDetailScreen(dish,false,RecipeUiState.Success(recipe),ReviseUiState.Done(revision),VideoUiState.Success(emptyList()),null,{},{},{},onRequest,{})
 }
 @Test fun actualDetailCopiesOnlyOnTapAndUsesTheVersionCurrentlyShown() {
  val manager=InstrumentationRegistry.getInstrumentation().targetContext.getSystemService(ClipboardManager::class.java)
  var prior:ClipData?=null
  rule.runOnIdle {prior=manager.primaryClip;manager.setPrimaryClip(ClipData.newPlainText("test","unchanged-until-tap"))}
  rule.setContent {MaterialTheme {Detail()}}
  fun copied():String {var value="";rule.runOnIdle {value=manager.primaryClip!!.getItemAt(0).text.toString()};return value}
  try {
   assertEquals("unchanged-until-tap",copied())
   rule.onNodeWithTag("copy-recipe-ingredients").performScrollTo().performClick()
   assertEquals(copyRecipeIngredients(dish.name,false,recipe.ingredients.map {it.name to it.amount}),copied())
   rule.onNodeWithTag("copy-recipe-steps").performScrollTo().performClick()
   assertEquals(copyRecipeSteps(dish.name,false,recipe.steps.map {it.text}),copied())
   rule.onNodeWithTag("revision-toggle").performScrollTo().performClick()
   rule.onNodeWithTag("copy-recipe-ingredients").performScrollTo().performClick()
   assertEquals(copyRecipeIngredients(dish.name,true,revision.ingredients.map {it.name to it.amount}),copied())
   rule.onNodeWithTag("copy-recipe-steps").performScrollTo().performClick()
   assertEquals(copyRecipeSteps(dish.name,true,revision.steps.map {it.text}),copied())
  } finally {rule.runOnIdle {if(prior!=null)manager.setPrimaryClip(prior!!) else if(android.os.Build.VERSION.SDK_INT>=28) manager.clearPrimaryClip() else manager.setPrimaryClip(ClipData.newPlainText("", ""))}}
 }
 @Test fun expandedChangesRemainReadableAndTogglingNeverRequestsAI() {
  var requests=0
  rule.setContent {
   val density=LocalDensity.current
   CompositionLocalProvider(LocalDensity provides Density(density.density,1.4f)) {MaterialTheme {Detail {requests++}}}
  }
  rule.onNodeWithTag("revision-toggle").performScrollTo().performClick()
  rule.onNodeWithTag("revision-changes-toggle").performScrollTo().performClick()
  rule.onNodeWithText("• 계란 대신 두부를 사용해요").performScrollTo().assertIsDisplayed()
  rule.onNodeWithText("재료: 계란").performScrollTo().assertIsDisplayed()
  rule.onNodeWithText("조리 단계: 1").performScrollTo().assertIsDisplayed()
  rule.onNodeWithTag("revision-changes-toggle").performScrollTo().performClick()
  rule.onNodeWithTag("recipe-change").assertDoesNotExist()
  rule.runOnIdle {assertEquals(0,requests)}
 }
 @Test fun loadingStopsAtBackgroundAndResumesWithoutMakingAnyRequest() {
  val owner=object:LifecycleOwner {
   val registry=LifecycleRegistry(this)
   override val lifecycle:Lifecycle get()=registry
  }
  rule.runOnIdle {owner.registry.currentState=Lifecycle.State.CREATED}
  rule.setContent {CompositionLocalProvider(LocalLifecycleOwner provides owner,LocalLoadingMotionOverride provides true) {MaterialTheme {IngredientLoading(LoadingTask.DISHES)}}}
  SystemClock.sleep(1150)
  rule.onNodeWithTag("loading-icon-0",useUnmergedTree=true).assertExists()
  rule.runOnIdle {owner.registry.currentState=Lifecycle.State.RESUMED}
  rule.waitUntil(4000) {rule.onAllNodesWithTag("loading-icon-1",useUnmergedTree=true).fetchSemanticsNodes().isNotEmpty()}
  rule.onNodeWithText("만들 수 있는 요리를 찾고 있어요").assertIsDisplayed()
  rule.runOnIdle {owner.registry.currentState=Lifecycle.State.DESTROYED}
 }
 @Test fun actualListHidesCardsWhileRefreshingAndLoadingTicksDoNotRepeatRequests() {
  var calls=0
  val gate=CompletableDeferred<Unit>()
  val api=object:DishApi {
   override suspend fun dishes()=DishCatalogResponse(emptyList(),0)
   override suspend fun videos(request:DishVideosRequest)=DishVideosResponse(emptyList())
   override suspend fun suggest(request:DishSuggestRequest):DishSuggestResponse {
    calls++
    if(calls==2) {gate.await();throw java.io.IOException("simulated network failure")}
    return DishSuggestResponse("mock",listOf(DishDto("demo","계란밥","밥",listOf("밥"),emptyList(),"",emptyList(),null)))
   }
  }
  val dishes=DishViewModel(api,debounceMillis=0)
  val fridge=FridgeViewModel().apply {addIngredients(listOf(Ingredient("밥")))}
  rule.setContent {MaterialTheme {RecipeScreen(fridge,dishes,{})}}
  try {
   rule.waitUntil {dishes.state is DishUiState.Success}
   rule.runOnIdle {dishes.retry()}
   rule.onNodeWithText("계란밥").assertDoesNotExist()
   rule.onNodeWithText("만들 수 있는 요리를 찾고 있어요").assertIsDisplayed()
   SystemClock.sleep(1300)
   rule.runOnIdle {assertEquals(2,calls)}
   gate.complete(Unit)
   rule.waitUntil {dishes.state is DishUiState.Error}
   rule.onNodeWithTag("recipe-list-progress").assertDoesNotExist()
   rule.onNodeWithText("계란밥").assertIsDisplayed()
   rule.onNodeWithText("다시 시도").performClick()
   rule.waitUntil {dishes.state is DishUiState.Success}
   rule.runOnIdle {assertEquals(3,calls)}
  } finally {gate.complete(Unit)}
 }
 @Test fun reducedMotionKeepsAStaticIconAndTruthfulTaskMessage() {
  rule.setContent {CompositionLocalProvider(LocalLoadingMotionOverride provides false) {MaterialTheme {IngredientLoading(LoadingTask.REVISION)}}}
  SystemClock.sleep(1150)
  rule.onNodeWithTag("loading-icon-0",useUnmergedTree=true).assertExists()
  rule.onNodeWithTag("loading-icon-1",useUnmergedTree=true).assertDoesNotExist()
  rule.onNodeWithText("내 재료에 맞게 레시피를 바꾸고 있어요").assertIsDisplayed()
  assertFalse(loadingMotionAllowed(0f,1f));assertFalse(loadingMotionAllowed(.5f,1f));assertTrue(loadingMotionAllowed(1f,1f))
 }
}
