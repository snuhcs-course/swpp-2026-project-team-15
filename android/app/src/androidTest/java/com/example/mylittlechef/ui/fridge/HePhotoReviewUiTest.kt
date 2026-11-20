// AI-assisted HE photo review regressions, 2026-11-09; manual review pending.
package com.example.mylittlechef.ui.fridge

import android.graphics.Bitmap
import android.graphics.Color
import androidx.compose.material3.MaterialTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.requiredSize
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.Density
import androidx.compose.ui.unit.dp
import androidx.compose.ui.graphics.asAndroidBitmap
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mylittlechef.data.local.FridgeRepository
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.domain.*
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.ui.fridge.add.AnalyzeScreen
import com.example.mylittlechef.viewmodel.*
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.MutableStateFlow
import okhttp3.MultipartBody
import org.junit.After
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.File
import java.io.IOException

class HePhotoReviewUiTest {
    @get:Rule val rule = createComposeRule()
    private val files = mutableListOf<File>()
    private val models = mutableListOf<PhotoAnalysisViewModel>()
    private val catalogApi = object : IngredientSupportApi {
        override suspend fun ingredientNames() = IngredientCatalogResponse(listOf("두부", "순두부"))
        override suspend fun ingredientSuggestions(request: IngredientSuggestionRequest) = error("Not used")
        override suspend fun analyze(image: MultipartBody.Part) = error("No live calls")
    }

    @After fun cleanup() {
        rule.runOnIdle { models.forEach { it.cancel() } }
        files.forEach { it.delete() }
    }

    private fun photo(color: Int = Color.GREEN): String {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val file = File.createTempFile("he-synthetic-", ".png", context.cacheDir)
        val bitmap = Bitmap.createBitmap(80, 60, Bitmap.Config.ARGB_8888)
        bitmap.eraseColor(color)
        file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        bitmap.recycle()
        files.add(file)
        return android.net.Uri.fromFile(file).toString()
    }

    private fun result(uris: List<String>, mode: RecognitionMode = RecognitionMode.LIVE): PhotoAnalysis =
        AnalyzeResponse(listOf(IngredientCandidateDto("두부", listOf("흰색 두부 포장"), .4)))
            .toPhotoAnalysis(uris).copy(mode = mode)

    private fun show(fridge: FridgeViewModel = FridgeViewModel(), source: String = photo(),
        onSaved: () -> Unit = {}, onManual: () -> Unit = {}, onRetake: () -> Unit = {},
        compact: Boolean = false, dark: Boolean = false, fontScale: Float = 1f,
        load: suspend (String) -> PhotoAnalysis = { result(listOf(it)) }): PhotoAnalysisViewModel {
        val vm = PhotoAnalysisViewModel(load).also { models.add(it) }
        val catalog = IngredientCatalogViewModel(catalogApi)
        rule.setContent { CompositionLocalProvider(
            LocalDensity provides Density(LocalDensity.current.density, fontScale)
        ) { com.example.mylittlechef.ui.theme.MyLittleChefTheme(darkTheme = dark, dynamicColor = false) {
            Box(if (compact) Modifier.requiredSize(320.dp, 400.dp).testTag("review-viewport") else Modifier) {
            AnalyzeScreen(fridge = fridge, onBackClick = {}, onManualClick = onManual,
                onRetakeClick = onRetake, onSaveClick = onSaved, imageUri = source,
                ingredientCatalog = catalog, reviewModel = vm)
        } } } }
        return vm
    }

    @Test fun smallLargeTextRecoveryKeepsRetryReachable() {
        var attempts = 0
        show(compact = true, fontScale = 2f) {
            attempts++
            if (attempts == 1) throw IOException("offline")
            PhotoAnalysis(emptyList(), listOf(it))
        }
        rule.onNodeWithText("다시 시도").assertIsDisplayed().performTouchInput { click() }
        rule.runOnIdle { assertEquals(2, attempts) }
    }

    @Test fun darkLargeTextReviewKeepsPhotoAndConfirmationVisible() {
        show(dark = true, fontScale = 1.7f)
        rule.onNodeWithTag("review-photo").assertIsDisplayed()
        rule.onNodeWithTag("confirm-photo-review").assertIsDisplayed().performClick()
        rule.onNodeWithTag("save-reviewed-ingredients").assertIsDisplayed().assertIsEnabled()
    }

    @Test fun photoAndEvidenceAreVisibleAndOnlyConfirmedNamesAreSaved() {
        val fridge = FridgeViewModel()
        var saved = false
        show(fridge = fridge, onSaved = { saved = true })
        rule.onNodeWithTag("review-photo").assertIsDisplayed()
        rule.onNodeWithText("인식한 내용: 흰색 두부 포장").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("확인 필요 · 사진과 비교해 주세요").assertIsDisplayed()
        rule.onNodeWithTag("save-reviewed-ingredients").assertIsNotEnabled()
        rule.onNodeWithTag("confirm-photo-review").performClick()
        rule.onNodeWithTag("save-reviewed-ingredients").performClick()
        rule.runOnIdle {
            assertTrue(saved)
            assertEquals(listOf(Ingredient("두부")), fridge.ingredients)
        }
    }

    @Test fun editingAfterConfirmationRequiresAnotherReview() {
        val vm = show()
        rule.onNodeWithTag("confirm-photo-review").performClick()
        rule.onNodeWithTag("save-reviewed-ingredients").assertIsEnabled()
        rule.onNodeWithText("두부", substring = false).performClick()
        rule.onNode(hasSetTextAction()).performTextReplacement("순두부")
        rule.onNodeWithTag("save-reviewed-ingredients").assertIsNotEnabled()
        rule.runOnIdle { assertEquals("두부", vm.editor.ingredients.single().recognition!!.suggestedName) }
    }

    @Test fun emptyResultIsDifferentFromErrorAndHasWorkingRecoveryActions() {
        var attempts = 0
        var manual = 0
        var retake = 0
        show(onManual = { manual++ }, onRetake = { retake++ }) {
            attempts++
            if (attempts == 1) throw IOException("private transport detail")
            PhotoAnalysis(emptyList(), listOf(it))
        }
        rule.onNodeWithText("인식을 완료하지 못했어요").assertIsDisplayed()
        rule.onNodeWithText("다시 시도").performClick()
        rule.onNodeWithText("재료를 찾지 못했어요").assertIsDisplayed()
        rule.onNodeWithText("직접 입력").performClick()
        rule.onNodeWithText("다시 찍기").performClick()
        rule.runOnIdle { assertEquals(2, attempts); assertEquals(1, manual); assertEquals(1, retake) }
    }

    @Test fun loadingCanBeCancelledWithoutSavingCandidates() {
        val gate = CompletableDeferred<Unit>()
        val fridge = FridgeViewModel()
        show(fridge) { gate.await(); result(listOf(it)) }
        rule.onNodeWithTag("recognition-progress").assertIsDisplayed()
        rule.onNodeWithText("인식 취소").performClick()
        gate.complete(Unit)
        rule.onNodeWithText("인식을 취소했어요").assertIsDisplayed()
        rule.onNodeWithTag("save-reviewed-ingredients").assertDoesNotExist()
        rule.runOnIdle { assertTrue(fridge.ingredients.isEmpty()) }
    }

    @Test fun mockResultsAreLabelledAndSeveralOriginalPhotosCanBeCompared() {
        val first = photo()
        val second = photo(Color.BLUE)
        show(source = first) { result(listOf(first, second), RecognitionMode.MOCK) }
        rule.onNodeWithText("샘플 결과예요. 사진을 분석한 결과가 아니에요.").assertIsDisplayed()
        rule.onNodeWithText("1/2").assertIsDisplayed()
        val screenshot = File(InstrumentationRegistry.getInstrumentation().targetContext.cacheDir, "he-photo-review.png")
        screenshot.outputStream().use { rule.onRoot().captureToImage().asAndroidBitmap().compress(Bitmap.CompressFormat.PNG, 100, it) }
        rule.onNodeWithText("다음 사진").performClick()
        rule.onNodeWithText("2/2").assertIsDisplayed()
        rule.onNodeWithText("이전 사진").performClick()
        rule.onNodeWithText("1/2").assertIsDisplayed()
    }

    @Test fun failedSaveKeepsReviewAndEditedRowsForRetry() {
        var fail = true
        var saved = false
        val store = object : FridgeRepository {
            override val names = MutableStateFlow(emptyList<String>())
            override suspend fun add(values: List<String>) {
                if (fail) throw IOException("disk")
                names.value = values
            }
            override suspend fun remove(value: String) = Unit
        }
        val fridge = FridgeViewModel(store)
        show(fridge, onSaved = { saved = true })
        rule.onNodeWithTag("confirm-photo-review").performClick()
        rule.onNodeWithTag("save-reviewed-ingredients").performClick()
        rule.onNodeWithText("재료를 저장하지 못했어요. 다시 시도해 주세요.").assertIsDisplayed()
        rule.runOnIdle { assertFalse(saved); assertTrue(fridge.ingredients.isEmpty()); fail = false }
        rule.onNodeWithTag("save-reviewed-ingredients").performClick()
        rule.waitUntil(5000) { saved }
        rule.runOnIdle { assertEquals(listOf("두부"), fridge.ingredients.map { it.name }) }
    }
}
