// Revision guidance and progressive cooking card shade checks assisted by Codex, 2026-11-24.
package com.example.mylittlechef.ui.recipe
import android.graphics.Bitmap
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.graphics.toPixelMap
import androidx.compose.ui.graphics.luminance
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mylittlechef.domain.*
import com.example.mylittlechef.viewmodel.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.File

class UatRevisionGuidanceUiTest {
 @get:Rule val rule=createComposeRule()
 private val dish=Dish("guidance","김치볶음밥","밥",listOf("밥"),listOf("김치"),"","",true)
 private val recipe=DishRecipe("guidance",dish.name,videoTitle=null,videoChannel=null,servings=1,
  ingredients=listOf(RecipeIngredient("밥","1공기",Availability.OWNED),RecipeIngredient("김치",null,Availability.UNAVAILABLE),RecipeIngredient("계란",null,Availability.UNAVAILABLE),RecipeIngredient("소금",null,Availability.ASSUMED)),
  steps=listOf(RecipeStep(1,"재료를 준비해요"),RecipeStep(2,"재료를 볶아요"),RecipeStep(3,"밥을 넣고 마무리해요")),tips=emptyList(),uncertain=emptyList(),captionGaps=false)
 private fun capture(name:String) {
  val i=InstrumentationRegistry.getInstrumentation();i.uiAutomation.waitForIdle(100,3000)
  File(i.targetContext.cacheDir,name).outputStream().use {requireNotNull(i.uiAutomation.takeScreenshot()).compress(Bitmap.CompressFormat.PNG,100,it)}
 }
 @Composable private fun Detail(revision:Revision) {
  MaterialTheme {RecipeDetailScreen(dish,false,RecipeUiState.Success(recipe),ReviseUiState.Done(revision),VideoUiState.Success(emptyList()),null,{},{},{},{},{})}
 }
 @Test fun confirmedRefusalShowsOnlyOriginalMissingIngredientsAndKeepsTheReason() {
  rule.setContent {Detail(Revision.Refused("김치가 없으면 이 요리를 만들기 어려워요."))}
  rule.onNodeWithTag("revise-refused").performScrollTo().assertIsDisplayed()
  rule.onNodeWithTag("revision-missing-ingredients").performScrollTo().assertIsDisplayed()
  val inside=hasAnyAncestor(hasTestTag("revision-missing-ingredients"))
  rule.onNode(inside and hasText("김치")).assertIsDisplayed()
  rule.onNode(inside and hasText("계란")).assertIsDisplayed()
  rule.onAllNodes(inside and hasText("소금")).assertCountEquals(0)
  rule.onAllNodes(inside and hasText("밥")).assertCountEquals(0)
  capture("revision-missing-guidance.png")
 }
 @Test fun failedGeneratedAnswerDoesNotBlameTheUsersInventory() {
  val message=revisionFailureMessage("bad_reference")
  rule.setContent {Detail(Revision.Failed(message))}
  rule.onNodeWithText(message).performScrollTo().assertIsDisplayed()
  rule.onNodeWithTag("revision-missing-ingredients").assertDoesNotExist()
  rule.onNodeWithTag("revise-refused").assertDoesNotExist()
  rule.onNodeWithTag("revise-retry").performScrollTo().assertIsDisplayed()
 }
 @Test fun cardsGetDarkerAndGoingBackRestoresTheSameShadeInBothThemes() {
  val run=startCookingRun(recipe)
  var dark by mutableStateOf(false)
  rule.setContent {MaterialTheme(colorScheme=if(dark) darkColorScheme() else lightColorScheme()) {CookingCards(run,{}, {})}}
  fun sample()=rule.onNodeWithTag("cooking-step-card").captureToImage().toPixelMap().let {it[it.width*9/10,it.height*9/10]}
  val first=sample();capture("cooking-first-shade.png")
  rule.onNodeWithTag("cooking-next").performClick();val second=sample()
  rule.onNodeWithTag("cooking-next").performClick();val last=sample()
  assertTrue(first.luminance()>second.luminance());assertTrue(second.luminance()>last.luminance())
  capture("cooking-last-shade.png")
  rule.onNodeWithTag("cooking-previous").performClick()
  assertEquals(second,sample())
  rule.runOnIdle {dark=true}
  val middleDark=sample()
  rule.onNodeWithTag("cooking-next").performClick()
  assertTrue(middleDark.luminance()>sample().luminance())
  rule.onNodeWithTag("cooking-step-text").assertTextEquals("밥을 넣고 마무리해요")
 }
}
