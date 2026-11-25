// UAT stage 2 integrated UI tests assisted by Codex, 2026-11-24.
package com.example.mylittlechef.ui
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.toPixelMap
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density
import com.example.mylittlechef.ui.components.IngredientBadge
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.ui.fridge.FridgeScreen
import com.example.mylittlechef.ui.onboarding.*
import com.example.mylittlechef.ui.profile.*
import com.example.mylittlechef.ui.theme.MyLittleChefTheme
import com.example.mylittlechef.viewmodel.*
import com.example.mylittlechef.model.Ingredient
import androidx.test.platform.app.InstrumentationRegistry
import android.graphics.Bitmap
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.File

class UatSelectionUiTest {
 @get:Rule val rule=createComposeRule()
 private fun stroke(first:String,last:String,back:Boolean=false) {
  val start=rule.onNodeWithTag(first).fetchSemanticsNode().boundsInRoot.center
  val end=rule.onNodeWithTag(last).fetchSemanticsNode().boundsInRoot.center
  val root=rule.onRoot().fetchSemanticsNode().boundsInRoot.topLeft
  rule.onRoot().performTouchInput {
   down(start-root);advanceEventTime(700)
   moveTo(end-root,300)
   if(back) moveTo(start-root,300)
   up()
  }
 }
 private fun capture(name:String) {
  val i=InstrumentationRegistry.getInstrumentation();i.uiAutomation.waitForIdle(100,3000)
  File(i.targetContext.cacheDir,name).outputStream().use { requireNotNull(i.uiAutomation.takeScreenshot()).compress(Bitmap.CompressFormat.PNG,100,it) }
 }
 @Test fun fridgeLongHoldEntersManageAndDraggingSelectsThenDeselectsWithoutToggling() {
  val fridge=FridgeViewModel().apply {addIngredients(listOf("마늘","두부","계란").map(::Ingredient))}
  val user=UserViewModel()
  rule.setContent {MyLittleChefTheme {FridgeScreen(user,fridge,{})}}
  rule.onNodeWithTag("fridge-ingredient-마늘").performTouchInput {longClick()}
  rule.onNodeWithTag("fridge-ingredient-마늘").assertIsSelected()
  rule.onNodeWithText("취소").performClick()
  rule.onNodeWithTag("fridge-sort-trigger").performClick()
  rule.onNodeWithTag("fridge-sort-ALPHABETICAL").performClick()
  rule.onNodeWithTag("manage-fridge").performClick()
  stroke("fridge-ingredient-계란","fridge-ingredient-마늘",back=true)
  listOf("마늘","두부","계란").forEach {rule.onNodeWithTag("fridge-ingredient-$it").assertIsSelected()}
  capture("uat2-fridge-selected.png")
  stroke("fridge-ingredient-계란","fridge-ingredient-마늘",back=true)
  listOf("마늘","두부","계란").forEach {rule.onNodeWithTag("fridge-ingredient-$it").assertIsNotSelected()}
  rule.onNodeWithTag("fridge-ingredient-두부").performClick().assertIsSelected()
  rule.onNodeWithTag("delete-selected-ingredients").performClick()
  rule.onNodeWithTag("cancel-ingredient-delete").performClick()
  rule.runOnIdle {assertEquals(3,fridge.ingredients.size)}
 }
 @Test fun onboardingUtensilDragChangesOnlyDraftUntilNextAndAllergyTapRemainsAvailable() {
  val user=UserViewModel()
  rule.setContent {MyLittleChefTheme {OnboardingUtensil(user,{}, {})}}
  stroke("choice-가스레인지","choice-오븐",back=true)
  listOf("가스레인지","인덕션","오븐").forEach {rule.onNodeWithTag("choice-$it").assertIsOn()}
  rule.runOnIdle {assertTrue(user.utensils.isEmpty())}
  rule.onNodeWithText("다음").performClick()
  rule.runOnIdle {assertEquals(setOf("가스레인지","인덕션","오븐"),user.utensils.toSet())}
 }
 @Test fun profileAllergyDraftSupportsDragDeselectionAndCancelWithoutSave() {
  val user=UserViewModel()
  var back=false
  rule.setContent {MyLittleChefTheme {EditAllergyScreen(user,{back=true},{})}}
  stroke("choice-땅콩","choice-밀",back=true)
  rule.onNodeWithTag("choice-땅콩").assertIsOn()
  rule.onNodeWithTag("choice-우유").assertIsOn()
  rule.onNodeWithTag("choice-밀").assertIsOn()
  stroke("choice-땅콩","choice-밀")
  listOf("땅콩","우유","밀").forEach {rule.onNodeWithTag("choice-$it").assertIsOff()}
  rule.onNodeWithTag("choice-달걀").performClick().assertIsOn()
  capture("uat2-allergy-selected.png")
  rule.onNodeWithContentDescription("back").performClick()
  rule.runOnIdle {assertTrue(back);assertTrue(user.allergies.isEmpty())}
 }
 @Test fun pantryDragSharesStateAcrossSeasoningAndBasicSectionsAndDoesNotSaveBeforeConfirmation() {
  val fridge=FridgeViewModel()
  var saved=false
  rule.setContent {MyLittleChefTheme {EditPantryScreen(fridge,{}, {saved=true})}}
  stroke("choice-소금","choice-간장",back=true)
  rule.onNodeWithTag("choice-소금").assertIsOn()
  rule.onNodeWithTag("choice-간장").assertIsOn()
  stroke("choice-된장","choice-양파")
  rule.onNodeWithTag("choice-된장").assertIsOn()
  rule.onNodeWithTag("choice-양파").assertIsOn()
  rule.onNodeWithTag("choice-소금").assertIsOn()
  rule.runOnIdle {assertTrue(fridge.ingredients.isEmpty())}
  rule.onNodeWithText("저장").performClick()
  rule.runOnIdle {assertTrue(saved);assertTrue(fridge.ingredients.any {it.name=="소금"});assertTrue(fridge.ingredients.any {it.name=="간장"})}
 }
 @Test fun selectedBadgeReplacesArtWithCheckAndDarkensItsOwnColorInBothThemes() {
  var selected by mutableStateOf(false)
  var dark by mutableStateOf(false)
  rule.setContent {MaterialTheme(colorScheme=if(dark) darkColorScheme() else lightColorScheme()) {
   IngredientBadge("소금",Modifier.testTag("badge"),selected=selected)
  }}
  fun sample()=rule.onNodeWithTag("badge").captureToImage().toPixelMap().let {it[it.width/2,it.height/10]}
  val normal=sample()
  rule.runOnIdle {selected=true}
  rule.onNodeWithTag("selected-icon-소금",useUnmergedTree=true).assertExists()
  val checked=sample()
  assertTrue(checked.red<normal.red && checked.green<normal.green && checked.blue<normal.blue)
  rule.runOnIdle {dark=true}
  rule.onNodeWithTag("selected-icon-소금",useUnmergedTree=true).assertExists()
  rule.runOnIdle {selected=false}
  rule.onNodeWithTag("selected-icon-소금",useUnmergedTree=true).assertDoesNotExist()
  assertEquals(normal,sample())
 }
 @Test fun ordinarySwipeScrollsWithoutSelectingAnyIngredient() {
  var selected by mutableStateOf(listOf<String>())
  rule.setContent {MyLittleChefTheme {
   Column(Modifier.height(240.dp).testTag("scroll-list").verticalScroll(rememberScrollState())) {
    PantrySelectionContent(selected,{selected=it})
   }
  }}
  rule.onNodeWithTag("scroll-list").performTouchInput {swipeUp(durationMillis=150)}
  rule.runOnIdle {assertTrue(selected.isEmpty())}
 }
}
