// Actual fridge and recipe refresh UI integration assisted by Codex, 2026-11-24.
package com.example.mylittlechef.ui.recipe
import android.graphics.Bitmap
import androidx.compose.foundation.layout.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.domain.*
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.navigation.MainScreen
import com.example.mylittlechef.ui.components.*
import com.example.mylittlechef.ui.fridge.*
import com.example.mylittlechef.ui.theme.MyLittleChefTheme
import com.example.mylittlechef.viewmodel.*
import kotlinx.coroutines.CompletableDeferred
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.File
class UatIngredientBrowsingUiTest {
 @get:Rule val rule=createComposeRule()
 private class Fake(val count:Int=20):DishApi {
  var calls=0;var received=emptyList<String>();var gate:CompletableDeferred<Unit>?=null;var fail=false
  override suspend fun dishes()=DishCatalogResponse(emptyList(),0)
  override suspend fun videos(request:DishVideosRequest)=DishVideosResponse(emptyList())
  override suspend fun suggest(request:DishSuggestRequest):DishSuggestResponse {
   calls++;received=request.ingredients;gate?.await()
   if(fail) throw java.io.IOException("offline")
   return DishSuggestResponse("mock",(1..count).map {DishDto("$it","검증 요리 $it","",listOf("두부"),if(it%2==0) emptyList() else listOf("밥"),"",emptyList(),null)})
  }
 }
 private fun capture(name:String) {
  val i=InstrumentationRegistry.getInstrumentation();i.uiAutomation.waitForIdle(100,3000)
  File(i.targetContext.cacheDir,name).outputStream().use {requireNotNull(i.uiAutomation.takeScreenshot()).compress(Bitmap.CompressFormat.PNG,100,it)}
 }
 private val user=UserViewModel()
 private val stock=FridgeViewModel().apply {addIngredients(listOf("두부","계란").map(::Ingredient))}
 @Test fun shortTapOpensSortedRelatedDishesAndCardNavigatesUsingWholeFridge() {
  val api=Fake(3);val vm=DishViewModel(api,0);val fridge=stock;var opened:String?=null
  rule.setContent {MyLittleChefTheme {MainScreen(user,fridge,{},{},{},{},dishViewModel=vm,onDishClick={opened=it})}}
  rule.onNodeWithTag("fridge-ingredient-두부").performClick()
  rule.waitUntil {vm.state is DishUiState.Success}
  rule.onNodeWithTag("ingredient-recipe-sheet").assertIsDisplayed()
  rule.onNodeWithText("두부로 만드는 요리").assertIsDisplayed()
  val ready=rule.onNodeWithTag("recipe-card-2").fetchSemanticsNode().boundsInRoot
  val missing=rule.onNodeWithTag("recipe-card-1").fetchSemanticsNode().boundsInRoot
  assertTrue(ready.top<missing.top);assertEquals(listOf("두부","계란"),api.received)
  capture("ingredient-related-recipes.png")
  rule.onNodeWithTag("recipe-card-2").performClick()
  rule.waitUntil {opened=="2"};rule.onNodeWithTag("ingredient-recipe-sheet").assertDoesNotExist()
  rule.runOnIdle {assertEquals(1,api.calls);assertEquals(2,fridge.ingredients.size)}
 }
 @Test fun longPressStillSelectsWithoutOpeningRecipesOrCallingServer() {
  val api=Fake();val vm=DishViewModel(api,0)
  rule.setContent {MyLittleChefTheme {MainScreen(user,stock,{},{},{},{},dishViewModel=vm)}}
  rule.onNodeWithTag("fridge-ingredient-두부").performTouchInput {longClick()}
  rule.onNodeWithTag("fridge-ingredient-두부").assertIsSelected()
  rule.onNodeWithTag("ingredient-recipe-sheet").assertDoesNotExist()
  rule.runOnIdle {assertEquals(0,api.calls)}
 }
 @Test fun emptyRelatedSheetCanRetryAndTransientResetClosesIt() {
  val api=Fake(0);val vm=DishViewModel(api,0);val transient=FridgeTransientState()
  rule.setContent {MyLittleChefTheme {Box(Modifier.safeDrawingPadding()) {
   FridgeScreen(user,stock,{},transient=transient,dishes=vm)
  }}}
  rule.onNodeWithTag("fridge-ingredient-두부").performClick()
  rule.onNodeWithText("현재 추천에는 이 재료를 활용한 요리가 없어요.").assertIsDisplayed()
  rule.onNodeWithText("다시 추천받기").performClick()
  rule.runOnIdle {assertEquals(2,api.calls);transient.reset()}
  rule.onNodeWithTag("ingredient-recipe-sheet").assertDoesNotExist()
 }
 @Test fun pullDownHidesCardsWhileLoadingThenReplacesBatchWithoutDuplicateRequests() {
  val api=Fake();val vm=DishViewModel(api,0);val gate=CompletableDeferred<Unit>()
  rule.setContent {CompositionLocalProvider(LocalLoadingMotionOverride provides false) {
   MyLittleChefTheme {Box(Modifier.safeDrawingPadding()) {RecipeScreen(stock,vm,{})}}
  }}
  rule.waitUntil {vm.state is DishUiState.Success}
  val first=vm.visibleSuggestions("").map {it.id}
  rule.runOnIdle {api.gate=gate;vm.selectSort(DishSort.NAME)}
  // Sorting keeps the current keyed item visible; the refresh gesture is explicitly from the top.
  rule.onNodeWithTag("recipe-list").performScrollToIndex(0)
  rule.onNodeWithTag("recipe-list").performTouchInput {swipeDown(durationMillis=450)}
  rule.waitUntil {api.calls==2}
  try {
   rule.onNodeWithTag("recipe-list-progress").assertIsDisplayed()
   rule.onNodeWithTag("recipe-list").assertDoesNotExist()
   first.forEach {rule.onNodeWithTag("recipe-card-$it").assertDoesNotExist()}
   capture("recipe-refresh-loading-only.png")
   assertEquals(first.toSet(),vm.visibleSuggestions("").map {it.id}.toSet())
   rule.onNodeWithTag("recipe-pull-refresh").performTouchInput {swipeDown(durationMillis=450)}
   rule.runOnIdle {assertEquals(2,api.calls)}
  } finally {gate.complete(Unit)}
  rule.waitUntil {vm.state is DishUiState.Success}
  val second=vm.visibleSuggestions("").map {it.id}
  assertTrue(second.none {it in first});assertEquals(DishSort.NAME,vm.sort)
  rule.onNodeWithText("다른 추천을 준비했어요.").assertIsDisplayed()
  rule.onNodeWithTag("recipe-card-${second.first()}").assertIsDisplayed()
  capture("recipe-pull-refresh.png")
 }
 @Test fun failedRefreshPreservesCardsAndRetryRecovers() {
  val api=Fake();val vm=DishViewModel(api,0)
  rule.setContent {MyLittleChefTheme {Box(Modifier.safeDrawingPadding()) {RecipeScreen(stock,vm,{})}}}
  rule.waitUntil {vm.state is DishUiState.Success};val first=vm.visibleSuggestions("").map {it.id}
  rule.runOnIdle {api.fail=true}
  rule.onNodeWithTag("recipe-list").performTouchInput {swipeDown(durationMillis=450)}
  rule.waitUntil {vm.state is DishUiState.Error}
  rule.onNodeWithTag("recipe-card-${first.first()}").assertIsDisplayed()
  rule.runOnIdle {api.fail=false}
  rule.onNodeWithText("다시 시도").performClick()
  rule.waitUntil {vm.state is DishUiState.Success}
  assertTrue(vm.visibleSuggestions("").map {it.id}.toSet()!=first.toSet())
 }
}
