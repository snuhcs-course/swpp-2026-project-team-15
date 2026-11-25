// UAT stage 1 integrated UI tests assisted by Codex, 2026-11-24.
package com.example.mylittlechef.ui.fridge
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density
import android.graphics.Bitmap
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.junit4.StateRestorationTester
import androidx.test.platform.app.InstrumentationRegistry
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import com.example.mylittlechef.data.local.*
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.navigation.MainScreen
import com.example.mylittlechef.viewmodel.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import okhttp3.MultipartBody
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.File
import java.util.UUID
class UatSuggestionFlowTest {
 @get:Rule val rule=createComposeRule()
 private fun capture(name:String) {
  val instrumentation=InstrumentationRegistry.getInstrumentation()
  instrumentation.uiAutomation.waitForIdle(100,3000)
  val image=requireNotNull(instrumentation.uiAutomation.takeScreenshot())
  File(instrumentation.targetContext.cacheDir,name).outputStream().use {image.compress(Bitmap.CompressFormat.PNG,100,it)}
 }
 private val api=object:IngredientSupportApi {
  override suspend fun ingredientNames()=IngredientCatalogResponse(listOf("계란"))
  override suspend fun ingredientSuggestions(request:IngredientSuggestionRequest)=IngredientSuggestionResponse(listOf(IngredientSuggestionDto("계란",2,10,listOf("계란밥"))))
  override suspend fun analyze(image:MultipartBody.Part):AnalyzeResponse=error("No paid calls")
 }
 @Test fun actualSuggestionSheetAddThenUndoPersistsOnlyItsOwnItem() {
  val file=File(InstrumentationRegistry.getInstrumentation().targetContext.cacheDir,"uat-${UUID.randomUUID()}.preferences_pb")
  val scope=CoroutineScope(Dispatchers.IO+SupervisorJob())
  val repo=PreferencesFridgeRepository(PreferenceDataStoreFactory.create(scope=scope,produceFile={file}))
  runBlocking {repo.add(listOf("마늘"))}
  lateinit var fridge:FridgeViewModel
  rule.runOnIdle {fridge=FridgeViewModel(repo)}
  val suggestions=IngredientSuggestionViewModel(api)
  var dark by mutableStateOf(false)
  var scale by mutableStateOf(1f)
  val user=UserViewModel()
  rule.setContent {
   val density=LocalDensity.current
   CompositionLocalProvider(LocalDensity provides Density(density.density,scale)) {
    MaterialTheme(colorScheme=if(dark) darkColorScheme() else lightColorScheme()) {
     FridgeScreen(user,fridge,{},ingredientSuggestions=suggestions)
    }
   }
  }
  try {
   rule.waitUntil {fridge.isLoaded}
   rule.onNodeWithTag("ingredient-suggestions").performClick()
   rule.onNodeWithTag("suggestion-add-계란").performScrollTo().performClick()
   rule.waitUntil {fridge.additionNotice?.kind==AdditionNoticeKind.ADDED}
   rule.onNodeWithText("‘계란’ 재료가 추가되었습니다").assertIsDisplayed()
   rule.onNodeWithTag("suggestion-feedback-action").assertIsDisplayed()
   capture("uat1-add-light.png")
   rule.runOnIdle {dark=true;scale=1.5f}
   rule.onNodeWithTag("suggestion-feedback-action").assertIsDisplayed()
   rule.onNodeWithText("‘계란’ 재료가 추가되었습니다").assertIsDisplayed()
   capture("uat1-add-dark-large.png")
   runBlocking {repo.add(listOf("두부"))}
   rule.onNodeWithTag("suggestion-feedback-action").performClick()
   rule.waitUntil {fridge.additionNotice?.kind==AdditionNoticeKind.UNDONE}
   assertEquals(listOf("마늘","두부"),runBlocking {repo.names.first()})
   rule.onNodeWithText("식재료 추천").assertIsDisplayed()
  } finally {scope.cancel();runBlocking {scope.coroutineContext[Job]!!.join()};file.delete()}
 }
 @Test fun failedAdditionCanBeRetriedInTheOpenSheetWithoutFalseSuccess() {
  val file=File(InstrumentationRegistry.getInstrumentation().targetContext.cacheDir,"uat-failure-${UUID.randomUUID()}.preferences_pb")
  val scope=CoroutineScope(Dispatchers.IO+SupervisorJob())
  val real=PreferencesFridgeRepository(PreferenceDataStoreFactory.create(scope=scope,produceFile={file}))
  var fail=true
  val repo=object:FridgeRepository by real {
   override suspend fun addSuggested(name:String,token:String):AdditionResult {
    if(fail)throw java.io.IOException("simulated disk failure")
    return real.addSuggested(name,token)
   }
  }
  lateinit var fridge:FridgeViewModel
  val suggestions=IngredientSuggestionViewModel(api)
  rule.runOnIdle {fridge=FridgeViewModel(repo)}
  val user=UserViewModel()
  rule.setContent {MaterialTheme {FridgeScreen(user,fridge,{},ingredientSuggestions=suggestions)}}
  try {
   rule.waitUntil {fridge.isLoaded}
   rule.onNodeWithTag("ingredient-suggestions").performClick()
   rule.onNodeWithTag("suggestion-add-계란").performScrollTo().performClick()
   rule.waitUntil {fridge.additionNotice?.kind==AdditionNoticeKind.ADD_ERROR}
   rule.onNodeWithText("‘계란’ 재료를 저장하지 못했어요").assertIsDisplayed()
   assertTrue(runBlocking {real.names.first()}.isEmpty())
   rule.runOnIdle {fail=false}
   rule.onNodeWithTag("suggestion-feedback-action").performClick()
   rule.waitUntil {fridge.additionNotice?.kind==AdditionNoticeKind.ADDED}
   rule.onNodeWithText("‘계란’ 재료가 추가되었습니다").assertIsDisplayed()
   assertEquals(listOf("계란"),runBlocking {real.names.first()})
   rule.onNodeWithTag("suggestion-add-계란").performScrollTo().performClick()
   rule.waitUntil {fridge.additionNotice?.kind==AdditionNoticeKind.DUPLICATE}
   assertEquals(listOf("계란"),runBlocking {real.names.first()})
  } finally {scope.cancel();runBlocking {scope.coroutineContext[Job]!!.join()};file.delete()}
 }
 @Test fun savedInstanceRestoreKeepsManagementUntilATabIsActuallyLeft() {
  val restoration=StateRestorationTester(rule)
  lateinit var fridge:FridgeViewModel
  rule.runOnIdle {fridge=FridgeViewModel().apply {addSuggested("두부");dismissAddition(additionNotice!!.id)}}
  val user=UserViewModel()
  restoration.setContent {MaterialTheme {FridgeScreen(user,fridge,{})}}
  rule.onNodeWithTag("manage-fridge").performClick()
  rule.onNodeWithTag("fridge-ingredient-두부").performClick()
  restoration.emulateSavedInstanceStateRestore()
  rule.onNodeWithTag("fridge-ingredient-두부").assertIsSelected()
  rule.onNodeWithTag("delete-selected-ingredients").assertIsEnabled()
 }
 @Test fun leavingFridgeResetsSelectionButKeepsSortAndInventory() {
  lateinit var fridge:FridgeViewModel
  rule.runOnIdle {fridge=FridgeViewModel().apply {addSuggested("두부");dismissAddition(additionNotice!!.id)}}
  val user=UserViewModel()
  val suggestions=IngredientSuggestionViewModel(api)
  rule.setContent {MaterialTheme {MainScreen(user,fridge,{},{},{},{},ingredientSuggestions=suggestions)}}
  rule.onNodeWithTag("fridge-sort-trigger").performClick()
  rule.onNodeWithTag("fridge-sort-ALPHABETICAL").performClick()
  rule.onNodeWithTag("manage-fridge").performClick()
  rule.onNodeWithTag("fridge-ingredient-두부").performClick()
  rule.onNodeWithTag("delete-selected-ingredients").assertIsEnabled()
  rule.onNodeWithContentDescription("내 정보",useUnmergedTree=true).performClick()
  rule.onNodeWithContentDescription("냉장고",useUnmergedTree=true).performClick()
  rule.onNodeWithTag("delete-selected-ingredients").assertDoesNotExist()
  rule.onNodeWithTag("manage-fridge").assertIsDisplayed()
  rule.onNodeWithText("정렬: 가나다순 ⌄").assertIsDisplayed()
  rule.runOnIdle {assertEquals(listOf("두부"),fridge.ingredients.map {it.name})}
 }
}
