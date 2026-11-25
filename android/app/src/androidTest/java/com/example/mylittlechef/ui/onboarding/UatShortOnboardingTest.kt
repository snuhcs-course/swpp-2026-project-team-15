// Shortened onboarding flow tests assisted by Codex, 2026-11-25.
package com.example.mylittlechef.ui.onboarding
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.junit4.StateRestorationTester
import com.example.mylittlechef.ui.theme.MyLittleChefTheme
import com.example.mylittlechef.viewmodel.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
class UatShortOnboardingTest {
 @get:Rule val rule=createComposeRule()
 private fun removedQuestionsAbsent() {
  rule.onNodeWithText("집에 어떤 조리 도구가 있나요?").assertDoesNotExist()
  rule.onNodeWithText("알레르기 정보를 알려주세요").assertDoesNotExist()
 }
 @Test fun nicknameGoesStraightToPantryBackKeepsDraftAndFinishPreservesProfile() {
  val user=UserViewModel(utensils=listOf("전자레인지"),allergies=listOf("우유"))
  val fridge=FridgeViewModel();var finished=0
  val restoration=StateRestorationTester(rule)
  restoration.setContent {MyLittleChefTheme {OnboardingScreen(user,fridge,{user.completeOnboarding();finished++})}}
  rule.onNodeWithText("별명").performTextInput("확인용")
  rule.onNodeWithText("다음").performClick()
  rule.onNodeWithText("집에 있는 기본 재료와 조미료").assertIsDisplayed();removedQuestionsAbsent()
  rule.onNodeWithText("소금").performClick()
  rule.onNodeWithContentDescription("뒤로").performClick()
  rule.onNodeWithText("확인용").assertIsDisplayed()
  rule.onNodeWithText("다음").performClick()
  restoration.emulateSavedInstanceStateRestore()
  rule.onNodeWithText("집에 있는 기본 재료와 조미료").assertIsDisplayed();removedQuestionsAbsent()
  rule.onNodeWithText("다음").performClick()
  rule.onNodeWithText("시작하기").performClick()
  rule.runOnIdle {
   assertEquals(1,finished);assertTrue(user.onboardingComplete)
   assertEquals("확인용",user.nickname)
   assertEquals(listOf("전자레인지"),user.utensils);assertEquals(listOf("우유"),user.allergies)
   assertTrue(fridge.ingredients.any {it.name=="소금"})
  }
 }
 @Test fun pantryCanBeSkippedWithoutIntroducingAllergyOrUtensilPrompts() {
  val user=UserViewModel();val fridge=FridgeViewModel();var finished=false
  rule.setContent {MyLittleChefTheme {OnboardingScreen(user,fridge,{finished=true})}}
  rule.onNodeWithText("다음").performClick()
  rule.onNodeWithText("집에 있는 기본 재료와 조미료").assertIsDisplayed();removedQuestionsAbsent()
  rule.onNodeWithText("건너뛰기").performClick()
  rule.onNodeWithText("시작하기").performClick()
  rule.runOnIdle {assertTrue(finished);assertTrue(user.utensils.isEmpty());assertTrue(user.allergies.isEmpty());assertTrue(fridge.ingredients.isEmpty())}
 }
}
