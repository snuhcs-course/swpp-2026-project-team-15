// UX2 behavior regressions assisted by Codex, 2026-11-19; human review pending.
package com.example.mylittlechef.ui.design
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.dp
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mylittlechef.data.local.SectionTourRepository
import com.example.mylittlechef.navigation.Routes
import com.example.mylittlechef.ui.help.*
import com.example.mylittlechef.ui.onboarding.*
import com.example.mylittlechef.ui.fridge.add.*
import com.example.mylittlechef.ui.theme.MyLittleChefTheme
import com.example.mylittlechef.viewmodel.*
import com.example.mylittlechef.data.remote.*
import okhttp3.MultipartBody
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.File
class Ux2RegressionTest {
    @get:Rule val rule=createComposeRule()
    @Test fun utensilTilesHaveDistinctIconsAndAccessibleCheckStates() {
        val user=UserViewModel()
        rule.setContent { MyLittleChefTheme { OnboardingUtensil(user,{}, {}) } }
        listOf("가스레인지","인덕션","오븐","에어프라이어","믹서기","전자레인지").forEach {
            rule.onNodeWithText(it).assertIsDisplayed().assertIsOff().assertHeightIsAtLeast(48.dp)
            rule.onNodeWithTag("choice-icon-$it",useUnmergedTree=true).assertExists()
        }
        rule.onNodeWithText("오븐").performClick().assertIsOn()
        rule.onNodeWithText("인덕션").assertIsOff()
    }
    @Test fun allergyTilesHaveIconsAndKeepIndividualSelections() {
        val user=UserViewModel()
        rule.setContent { MyLittleChefTheme { OnboardingAllergy(user,{}, {}) } }
        listOf("땅콩","우유","밀","달걀","견과류","갑각류","생선","대두").forEach {
            rule.onNodeWithText(it).assertIsDisplayed().assertIsOff()
            rule.onNodeWithTag("choice-icon-$it",useUnmergedTree=true).assertExists()
        }
        rule.onNodeWithText("밀").performClick().assertIsOn()
        rule.onNodeWithText("달걀").performClick().assertIsOn()
        rule.onNodeWithText("우유").assertIsOff()
    }
    @Test fun nicknameSitsInMiddleLowerViewport() {
        val user=UserViewModel()
        rule.setContent { MyLittleChefTheme { Box(Modifier.requiredSize(360.dp,720.dp)) {OnboardingNickname(user,{})} } }
        val input=rule.onNode(hasSetTextAction()).getUnclippedBoundsInRoot()
        assertTrue((input.top+input.bottom)/2>340.dp && (input.top+input.bottom)/2<560.dp)
        rule.onNodeWithText("다음").assertIsDisplayed()
    }
    @Test fun draftDismissCanBeCancelledWithoutLosingInput() {
        var closed=false
        rule.setContent { MyLittleChefTheme { EntrySheet(onClose={closed=true}) {
            val controls=LocalEntrySheet.current!!
            SideEffect {controls.draft=true}
            Column { Text("작성 중인 재료"); TextButton(onClick={controls.requestClose()}) {Text("시트 닫기")} }
        } } }
        rule.onNodeWithText("시트 닫기").performClick()
        rule.onNodeWithText("계속 입력").performClick()
        rule.onNodeWithText("작성 중인 재료").assertExists()
        rule.runOnIdle {assertFalse(closed)}
        rule.onNodeWithText("시트 닫기").performClick()
        rule.onNodeWithTag("discard-entry-draft").performClick()
        rule.runOnIdle {assertTrue(closed)}
    }
    @Test fun savingBlocksSheetClose() {
        var closed=false
        rule.setContent { MyLittleChefTheme { EntrySheet(onClose={closed=true}) {
            val controls=LocalEntrySheet.current!!
            SideEffect {controls.busy=true;controls.draft=true}
            TextButton(onClick={controls.requestClose()}) {Text("시트 닫기")}
        } } }
        rule.onNodeWithText("시트 닫기").performClick()
        rule.onNodeWithTag("discard-entry-draft").assertDoesNotExist()
        rule.runOnIdle {assertFalse(closed)}
    }
    @Test fun actualTabTourPersistsCompletionAndReplaysFromProfile() {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val file=File.createTempFile("ux2-tour", ".preferences_pb",context.cacheDir).apply {delete()}
        val job=SupervisorJob()
        val repo=SectionTourRepository(PreferenceDataStoreFactory.create(scope=CoroutineScope(Dispatchers.IO+job),produceFile={file}))
        var route by mutableStateOf(Routes.FRIDGE)
        try {
            rule.setContent { MyLittleChefTheme { SectionTourHost(repo,route,{route=it}) {
                val tour=LocalSectionTour.current!!
                Column {
                    Text(route,Modifier.testTag("actual-tab"))
                    Box(Modifier.size(60.dp).tourAnchor(when(route) {Routes.RECIPE->"recipe-browse";Routes.PROFILE->"profile-pantry";else->"fridge-add"}))
                    TextButton(onClick={tour.launch()}){Text("다시 둘러보기")}
                }
            } } }
            rule.waitUntil(5000) {rule.onAllNodesWithTag("section-tour").fetchSemanticsNodes().isNotEmpty()}
            rule.onNodeWithTag("next-section-tour").performClick()
            rule.runOnIdle {assertEquals(Routes.FRIDGE,route)}
            rule.onNodeWithTag("next-section-tour").performClick()
            rule.runOnIdle {assertEquals(Routes.RECIPE,route)}
            rule.onNodeWithTag("next-section-tour").performClick()
            rule.runOnIdle {assertEquals(Routes.PROFILE,route)}
            rule.onNodeWithTag("next-section-tour").performClick()
            rule.waitUntil(5000) {rule.onAllNodesWithTag("section-tour").fetchSemanticsNodes().isEmpty()}
            runBlocking {assertEquals(1,repo.seenVersion.first())}
            rule.runOnIdle {route=Routes.PROFILE}
            rule.onNodeWithText("다시 둘러보기").performClick()
            rule.onNodeWithTag("skip-section-tour").performClick()
            rule.waitUntil(5000) {rule.onAllNodesWithTag("section-tour").fetchSemanticsNodes().isEmpty()}
            rule.runOnIdle {assertEquals(Routes.PROFILE,route)}
        } finally {runBlocking {job.cancelAndJoin()};file.delete()}
    }
    @Test fun automaticGuideWaitsUntilOnboardingIsComplete() {
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val file=File.createTempFile("ux2-tour-gate", ".preferences_pb",context.cacheDir).apply {delete()}
        val job=SupervisorJob()
        val repo=SectionTourRepository(PreferenceDataStoreFactory.create(scope=CoroutineScope(Dispatchers.IO+job),produceFile={file}))
        var enabled by mutableStateOf(false)
        try {
            rule.setContent { MyLittleChefTheme {
                val loaded by repo.seenVersion.collectAsState(initial=-1)
                SectionTourHost(repo,Routes.FRIDGE,{},automaticEnabled=enabled) { Text("loaded-$loaded") }
            } }
            rule.waitUntil(5000) {rule.onAllNodesWithText("loaded-0").fetchSemanticsNodes().isNotEmpty()}
            rule.onNodeWithTag("section-tour").assertDoesNotExist()
            rule.runOnIdle {enabled=true}
            rule.waitUntil(5000) {rule.onAllNodesWithTag("section-tour").fetchSemanticsNodes().isNotEmpty()}
            rule.onNodeWithTag("skip-section-tour").performClick()
            rule.waitUntil(5000) {rule.onAllNodesWithTag("section-tour").fetchSemanticsNodes().isEmpty()}
        } finally {runBlocking {job.cancelAndJoin()};file.delete()}
    }

    private fun catalog() = IngredientCatalogViewModel(object: IngredientSupportApi {
        override suspend fun ingredientNames()=IngredientCatalogResponse(listOf("무","두부"))
        override suspend fun ingredientSuggestions(request: IngredientSuggestionRequest)=error("Not used")
        override suspend fun analyze(image: MultipartBody.Part)=error("Not used")
    })
    @Test fun typingInRealManualScreenUpdatesSheetDismissGuard() {
        val fridge=FridgeViewModel();val catalog=catalog()
        var open by mutableStateOf(true)
        rule.setContent { MyLittleChefTheme { if(open) EntrySheet(onClose={open=false}) {
            val controls=LocalEntrySheet.current!!
            ManualAddScreen(fridge,catalog,{controls.requestClose()},{controls.complete()})
        } } }
        rule.onNode(hasSetTextAction()).performTextInput("무")
        rule.onNodeWithContentDescription("닫기").performClick()
        rule.onNodeWithText("계속 입력").assertIsDisplayed().performClick()
        rule.onNode(hasSetTextAction()).assertTextContains("무")
        rule.onNodeWithContentDescription("닫기").performClick()
        rule.onNodeWithTag("discard-entry-draft").performClick()
        rule.waitUntil(5000) {rule.onAllNodesWithTag("ingredient-entry-sheet").fetchSemanticsNodes().isEmpty()}
        rule.runOnIdle {assertTrue(fridge.ingredients.isEmpty())}
    }
    @Test fun realManualSaveClosesAnimatedSheetOnce() {
        val fridge=FridgeViewModel();val catalog=catalog()
        var open by mutableStateOf(true);var saved=0
        rule.setContent { MyLittleChefTheme { if(open) EntrySheet(onClose={open=false}) {
            val controls=LocalEntrySheet.current!!
            ManualAddScreen(fridge,catalog,{controls.requestClose()},{saved++;controls.complete()})
        } } }
        rule.onNode(hasSetTextAction()).performTextInput("무")
        rule.onNodeWithText("저장").assertIsDisplayed().performClick()
        rule.waitUntil(5000) {rule.onAllNodesWithTag("ingredient-entry-sheet").fetchSemanticsNodes().isEmpty()}
        rule.runOnIdle {assertEquals(1,saved);assertEquals(listOf("무"),fridge.ingredients.map{it.name})}
    }

}
