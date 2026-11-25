// Retired settings integration tests assisted by Codex, 2026-11-25.
package com.example.mylittlechef.ui
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.navigation.MainScreen
import com.example.mylittlechef.ui.profile.ProfileScreen
import com.example.mylittlechef.ui.theme.MyLittleChefTheme
import com.example.mylittlechef.viewmodel.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
class UatProfileScopeTest {
 @get:Rule val rule=createComposeRule()
 @Test fun profileTabShowsCurrentSettingsOnlyAndPreservesStoredProfile() {
  val user=UserViewModel(nickname="확인용",utensils=listOf("전자레인지"),allergies=listOf("우유"))
  val fridge=FridgeViewModel();var nickname=0;var pantry=0;var retired=0
  rule.setContent {MyLittleChefTheme {MainScreen(user,fridge,{},{nickname++},{retired++},{retired++},onEditPantryClick={pantry++})}}
  rule.onNodeWithContentDescription("내 정보",useUnmergedTree=true).performClick()
  rule.onNodeWithText("별명").assertIsDisplayed()
  rule.onNodeWithText("기본 재료·조미료").assertIsDisplayed()
  rule.onNodeWithText("알레르기").assertDoesNotExist()
  rule.onNodeWithText("조리 도구").assertDoesNotExist()
  rule.onNodeWithText("우유").assertDoesNotExist()
  rule.onNodeWithText("전자레인지").assertDoesNotExist()
  rule.onNodeWithText("별명").performClick()
  rule.onNodeWithText("기본 재료·조미료").performClick()
  rule.runOnIdle {
   assertEquals(1,nickname);assertEquals(1,pantry);assertEquals(0,retired)
   assertEquals(listOf("전자레인지"),user.utensils);assertEquals(listOf("우유"),user.allergies)
  }
 }
 @Test fun fallbackHelpDoesNotAdvertiseRetiredSettings() {
  val user=UserViewModel();val fridge=FridgeViewModel()
  rule.setContent {MyLittleChefTheme {ProfileScreen(user,fridge,{},{},{},{})}}
  rule.onNodeWithText("사용 안내").performClick()
  rule.onAllNodesWithText("알레르기",substring=true).assertCountEquals(0)
  rule.onAllNodesWithText("조리도구",substring=true).assertCountEquals(0)
  rule.onAllNodesWithText("조리 도구",substring=true).assertCountEquals(0)
 }
}
