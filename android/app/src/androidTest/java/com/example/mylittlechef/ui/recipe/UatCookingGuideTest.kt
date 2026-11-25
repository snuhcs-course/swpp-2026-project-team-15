// UAT stage 4 integrated UI tests assisted by Codex, 2026-11-24.
package com.example.mylittlechef.ui.recipe
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.SemanticsProperties
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.junit4.StateRestorationTester
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mylittlechef.data.local.*
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.domain.*
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.navigation.MainScreen
import com.example.mylittlechef.viewmodel.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.File
import java.util.UUID

class UatCookingGuideTest {
 @get:Rule val rule=createComposeRule()
 private fun mark(value:String) {InstrumentationRegistry.getInstrumentation().sendStatus(2,android.os.Bundle().apply {putString("uat-debug",value)})}
 private fun ready(tag:String) {rule.waitUntil(5000) {
  rule.onAllNodesWithTag(tag).fetchSemanticsNodes().firstOrNull()?.let { !it.config.contains(SemanticsProperties.Disabled) } == true
 }}
 private val dish=Dish("cook","계란밥","밥",listOf("밥"),emptyList(),"","",true)
 private val recipe=DishRecipe("cook","계란밥",videoTitle=null,videoChannel=null,servings=1,
  ingredients=listOf(RecipeIngredient("밥","1공기",Availability.OWNED),RecipeIngredient("계란","1개",Availability.OWNED),RecipeIngredient("소금","조금",Availability.ASSUMED)),
  steps=listOf(RecipeStep(1,"계란을 볶아요"),RecipeStep(2,"밥을 섞어요")),tips=emptyList(),uncertain=emptyList(),captionGaps=false)
 private val revised=Revision.Revised(1,listOf(RevisedIngredient("두부","반 모")),listOf(RecipeStep(1,"두부를 볶아요")),emptyList(),emptyList())
 @Composable private fun Detail(fridge:FridgeViewModel,revision:ReviseUiState?=null) {
  RecipeDetailScreen(dish,false,RecipeUiState.Success(recipe),revision,VideoUiState.Success(emptyList()),fridge,{},{},{},{},{})
 }
 @Test fun stepsSurviveStateRestoreAndExplicitExitRestartsAtFirstStepWithoutTouchingInventory() {
  val fridge=FridgeViewModel().apply {addIngredients(listOf(Ingredient("계란")))}
  val restoration=StateRestorationTester(rule)
  restoration.setContent {MaterialTheme {Detail(fridge)}}
  rule.onNodeWithTag("start-cooking").performScrollTo().performClick()
  rule.onNodeWithTag("cooking-step-number").assertTextEquals("1 / 2 단계")
  rule.onNodeWithTag("cooking-next").performClick()
  rule.onNodeWithTag("cooking-step-text").assertTextEquals("밥을 섞어요")
  restoration.emulateSavedInstanceStateRestore()
  rule.onNodeWithTag("cooking-step-number").assertTextEquals("2 / 2 단계")
  rule.onNodeWithTag("exit-cooking").performClick()
  rule.onNodeWithTag("confirm-exit-cooking").performClick()
  rule.onNodeWithTag("cooking-mode").assertDoesNotExist()
  rule.onNodeWithText("소진한 재료가 있나요?").assertDoesNotExist()
  rule.runOnIdle {assertEquals(listOf("계란"),fridge.ingredients.map {it.name})}
  rule.onNodeWithTag("start-cooking").performScrollTo().performClick()
  rule.onNodeWithTag("cooking-step-number").assertTextEquals("1 / 2 단계")
 }
 @Test fun revisedCookingCompletionOffersOnlyItsHeldIngredientsAndNothingStartsChecked() {
  val fridge=FridgeViewModel().apply {addIngredients(listOf("계란","두부","김치").map(::Ingredient))}
  rule.setContent {MaterialTheme {Detail(fridge,ReviseUiState.Done(revised))}}
  rule.onNodeWithTag("revision-toggle").performScrollTo().performClick()
  rule.onNodeWithTag("start-cooking").performScrollTo().performClick()
  rule.onNodeWithText("AI 수정본으로 조리 중").assertIsDisplayed()
  rule.onNodeWithTag("cooking-step-text").assertTextEquals("두부를 볶아요")
  rule.onNodeWithTag("cooking-next").performClick()
  rule.onNodeWithTag("consumed-두부").assertIsOff()
  rule.onNodeWithTag("consumed-계란").assertDoesNotExist()
  rule.onNodeWithTag("consumed-confirm").assertIsNotEnabled()
  rule.onNodeWithText("그대로 두기").performClick()
  rule.runOnIdle {assertEquals(3,fridge.ingredients.size)}
 }
 @Test fun longCookingStepScrollsAtLargeTextWhileNavigationRemainsReachable() {
  val run=startCookingRun(recipe.copy(steps=listOf(RecipeStep(1,"재료를 천천히 볶고 상태를 확인해요. ".repeat(120)),RecipeStep(2,"마무리해요"))))
  rule.setContent {
   val density=LocalDensity.current
   CompositionLocalProvider(LocalDensity provides Density(density.density,1.7f)) {MaterialTheme {CookingCards(run,{}, {})}}
  }
  rule.onNodeWithTag("cooking-previous").assertIsNotEnabled()
  rule.onNodeWithTag("cooking-next").assertIsDisplayed()
  rule.onNodeWithTag("cooking-step-scroll").performTouchInput {swipeUp()}
  val range=rule.onNodeWithTag("cooking-step-scroll").fetchSemanticsNode().config[SemanticsProperties.VerticalScrollAxisRange]
  assertTrue(range.value()>0f)
  rule.onNodeWithTag("cooking-next").performClick()
  rule.onNodeWithTag("cooking-step-number").assertTextEquals("2 / 2 단계")
  rule.onNodeWithTag("cooking-previous").performClick()
  rule.onNodeWithTag("cooking-step-number").assertTextEquals("1 / 2 단계")
 }
 @Test fun completionSaveFailureRetryAndUndoPreserveOtherIngredientsInRealLocalStore() {
  val file=File(InstrumentationRegistry.getInstrumentation().targetContext.cacheDir,"uat-cook-${UUID.randomUUID()}.preferences_pb")
  val job=SupervisorJob()
  val real=PreferencesFridgeRepository(PreferenceDataStoreFactory.create(scope=CoroutineScope(Dispatchers.IO+job),produceFile={file}))
  var fail=true
  val repo=object:FridgeRepository by real {
   override suspend fun removeAll(values:Set<String>) {if(fail) throw java.io.IOException("disk");real.removeAll(values)}
  }
  runBlocking {real.add(listOf("밥","계란","소금","김치"))}
  lateinit var fridge:FridgeViewModel
  rule.runOnIdle {fridge=FridgeViewModel(repo)}
  rule.setContent {MaterialTheme {Detail(fridge)}}
  try {
   rule.waitUntil {fridge.isLoaded}
   rule.onNodeWithTag("recipe-complete").performScrollTo().performClick()
   rule.onNodeWithTag("consumed-계란").assertIsOff()
   rule.onNodeWithTag("consumed-소금").assertIsOff()
   rule.onNodeWithTag("consumed-confirm").assertIsNotEnabled()
   rule.onNodeWithTag("consumed-계란").performClick()
   rule.onNodeWithTag("consumed-confirm").performClick()
   rule.waitUntil {fridge.removalError!=null}
   assertEquals(4,runBlocking {real.names.first()}.size)
   rule.runOnIdle {fail=false}
   rule.onNodeWithTag("consumed-confirm").performClick()
   rule.waitUntil {fridge.pendingRemoval!=null}
   rule.onNodeWithText("재료를 정리했어요").assertIsDisplayed()
   assertEquals(listOf("밥","소금","김치"),runBlocking {real.names.first()})
   rule.onNodeWithText("실행 취소").performClick()
   rule.waitUntil {fridge.pendingRemoval==null}
   assertEquals(listOf("밥","계란","소금","김치"),runBlocking {real.names.first()})
  } finally {runBlocking {job.cancelAndJoin()};file.delete()}
 }
 @Test fun realTabsTourAvoidsItsTargetAtLargeTextAndNeverRequestsRecipesOrMutatesInventory() {
  val file=File(InstrumentationRegistry.getInstrumentation().targetContext.cacheDir,"uat-tour-${UUID.randomUUID()}.preferences_pb")
  val job=SupervisorJob()
  val tour=SectionTourRepository(PreferenceDataStoreFactory.create(scope=CoroutineScope(Dispatchers.IO+job),produceFile={file}))
  var calls=0;var actions=0
  val api=object:DishApi {
   override suspend fun dishes()=DishCatalogResponse(emptyList(),0)
   override suspend fun videos(request:DishVideosRequest)=DishVideosResponse(emptyList())
   override suspend fun suggest(request:DishSuggestRequest):DishSuggestResponse {calls++;return DishSuggestResponse("mock",emptyList())}
  }
  val dishes=DishViewModel(api,debounceMillis=0)
  val user=UserViewModel().apply {completeOnboarding()}
  val fridge=FridgeViewModel().apply {addIngredients(listOf(Ingredient("밥")))}
  rule.setContent {
   val density=LocalDensity.current
   CompositionLocalProvider(LocalDensity provides Density(density.density,1.5f)) {
    MaterialTheme {Box(Modifier.requiredSize(360.dp,640.dp)) {
     MainScreen(user,fridge,{actions++},{actions++},{actions++},{actions++},dishViewModel=dishes,tourStore=tour)
    }}
   }
  }
  try {
   rule.waitUntil(5000) {rule.onAllNodesWithTag("section-tour").fetchSemanticsNodes().isNotEmpty()}
   repeat(4) { index ->
    mark("step=$index")
    rule.waitUntil(5000) {rule.onAllNodesWithTag("tour-highlight",useUnmergedTree=true).fetchSemanticsNodes().isNotEmpty()}
    mark("target located")
    val target=rule.onNodeWithTag("tour-highlight",useUnmergedTree=true).fetchSemanticsNode().boundsInRoot
    val card=rule.onNodeWithTag("tour-callout",useUnmergedTree=true).fetchSemanticsNode().boundsInRoot
    assertFalse("Guide must not cover its target",target.overlaps(card))
    if(index==3) {
     ready("previous-section-tour")
     rule.onNodeWithTag("previous-section-tour").performScrollTo().assertIsDisplayed().performClick()
     ready("next-section-tour")
     ready("next-section-tour")
    rule.onNodeWithTag("next-section-tour").performScrollTo().performClick()
    }
    ready("next-section-tour")
    rule.onNodeWithTag("next-section-tour").performScrollTo().assertIsDisplayed().performClick()
   }
   rule.waitUntil(5000) {rule.onAllNodesWithTag("section-tour").fetchSemanticsNodes().isEmpty()}
   mark("first tour completed")
   rule.runOnIdle {assertEquals(0,calls);assertEquals(0,actions);assertEquals(listOf("밥"),fridge.ingredients.map {it.name})}
   rule.onNodeWithContentDescription("내 정보",useUnmergedTree=true).performClick()
   rule.onNodeWithText("사용 안내").performScrollTo().performClick()
   rule.onNodeWithTag("skip-section-tour").performScrollTo().assertIsDisplayed().performClick()
   rule.waitUntil(5000) {rule.onAllNodesWithTag("section-tour").fetchSemanticsNodes().isEmpty()}
   rule.onNodeWithText("사용 안내").performScrollTo().assertIsDisplayed()
   mark("profile visible after replay")
   assertEquals(1,runBlocking {tour.seenVersion.first()})
   rule.mainClock.advanceTimeBy(1000)
   rule.waitForIdle()
  } catch(error:Throwable) {
   mark("primary failure: "+error.stackTraceToString())
   android.util.Log.e("UAT4","guide primary failure",error)
   throw error
  } finally {rule.waitForIdle();runBlocking {job.cancelAndJoin()};file.delete()}
 }
}
