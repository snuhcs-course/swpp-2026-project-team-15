// AI-assisted blocked-write recreation regressions, 2026-11-09; manual review pending.
package com.example.mylittlechef.ui.fridge

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.remember
import androidx.compose.runtime.CompositionLocalProvider
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.StateRestorationTester
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.data.local.FridgeRepository
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.ui.fridge.add.ManualAddScreen
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.IngredientCatalogViewModel
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.MutableStateFlow
import okhttp3.MultipartBody
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class HeSaveLifecycleUiTest {
    @get:Rule val rule = createComposeRule()
    private val api = object : IngredientSupportApi {
        override suspend fun ingredientNames() = IngredientCatalogResponse(listOf("두부", "무"))
        override suspend fun ingredientSuggestions(request: IngredientSuggestionRequest) = error("Not used")
        override suspend fun analyze(image: MultipartBody.Part) = error("No live calls")
        override suspend fun recommend(request: RecommendRequest) = error("Not used")
    }

    @Test fun saveCompletionWaitsForResumedOwnerAndIsConsumedOnlyOnce() {
        val fridge = FridgeViewModel()
        val catalog = IngredientCatalogViewModel(api)
        var navigations = 0
        lateinit var registry: LifecycleRegistry
        lateinit var owner: LifecycleOwner
        rule.runOnUiThread {
            owner = object : LifecycleOwner { override val lifecycle: Lifecycle get() = registry }
            registry = LifecycleRegistry(owner).apply { currentState = Lifecycle.State.STARTED }
        }
        rule.setContent { CompositionLocalProvider(LocalLifecycleOwner provides owner) {
            MaterialTheme { ManualAddScreen(fridge, catalog, {}, { navigations++ }) }
        } }
        rule.onNode(hasSetTextAction()).performTextInput("두부")
        rule.onNodeWithText("저장").performClick()
        rule.runOnIdle {
            assertEquals(0, navigations)
            assertNotNull(fridge.ingredientSaveCompletion)
            registry.currentState = Lifecycle.State.RESUMED
        }
        rule.waitUntil(5000) { navigations == 1 }
        rule.runOnIdle {
            registry.currentState = Lifecycle.State.STARTED
            registry.currentState = Lifecycle.State.RESUMED
        }
        rule.runOnIdle { assertEquals(1, navigations); assertNull(fridge.ingredientSaveCompletion) }
    }

    @Test fun typedRowsSurviveRecreationWithoutAnAutomaticKeyboardRequest() {
        val restorer = StateRestorationTester(rule)
        val fridge = FridgeViewModel()
        val catalog = IngredientCatalogViewModel(api)
        restorer.setContent { MaterialTheme { ManualAddScreen(fridge, catalog, {}, {}) } }
        rule.onNode(hasSetTextAction()).performTextInput("두부")
        rule.onNodeWithText("+ 식재료 추가").performScrollTo().performClick()
        rule.onNode(hasSetTextAction()).performTextInput("무")
        restorer.emulateSavedInstanceStateRestore()
        rule.onNodeWithText("두부", substring = false).assertExists()
        rule.onNode(hasSetTextAction()).assertTextContains("무")
    }

    @Test fun blockedSaveCompletesThroughTheRecreatedScreensCallbackOnlyOnce() {
        val gate = CompletableDeferred<Unit>()
        val source = object : FridgeRepository {
            override val names = MutableStateFlow(emptyList<String>())
            override suspend fun add(values: List<String>) { gate.await(); names.value = values }
            override suspend fun remove(value: String) = Unit
        }
        val fridge = FridgeViewModel(source)
        val catalog = IngredientCatalogViewModel(api)
        val restorer = StateRestorationTester(rule)
        var generation = 0
        val navigations = mutableListOf<Int>()
        restorer.setContent {
            val thisScreen = remember { ++generation }
            MaterialTheme { ManualAddScreen(fridge, catalog, {}, { navigations.add(thisScreen) }) }
        }
        try {
            rule.onNode(hasSetTextAction()).performTextInput("두부")
            rule.onNodeWithText("저장").performClick()
            restorer.emulateSavedInstanceStateRestore()
            gate.complete(Unit)
            rule.waitUntil(5000) { navigations.isNotEmpty() }
            rule.runOnIdle {
                assertEquals(listOf(generation), navigations)
                assertEquals(listOf("두부"), fridge.ingredients.map { it.name })
            }
        } finally { gate.complete(Unit) }
    }
}
