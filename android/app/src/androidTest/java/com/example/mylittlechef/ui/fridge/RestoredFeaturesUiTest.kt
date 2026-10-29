package com.example.mylittlechef.ui.fridge

import com.example.mylittlechef.data.local.FridgeRepository
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.flow.MutableStateFlow
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.ui.fridge.components.EditableIngredientList
import com.example.mylittlechef.ui.fridge.components.IngredientEditorState
import com.example.mylittlechef.ui.profile.EditPantryScreen
import com.example.mylittlechef.viewmodel.*
import okhttp3.MultipartBody
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class RestoredFeaturesUiTest {
    @get:Rule val rule = createComposeRule()

    @Test fun profilePantryEditorSavesAndPreservesNonPresetIngredients() {
        val fridge = FridgeViewModel().apply { addIngredients(listOf(Ingredient("소금"), Ingredient("생강"))) }
        var saved = false
        rule.setContent { MaterialTheme { EditPantryScreen(fridge, {}, { saved = true }) } }
        rule.onNodeWithText("소금").performClick()
        rule.onNodeWithText("설탕").performClick()
        rule.onNodeWithText("저장").performClick()
        rule.runOnIdle {
            assertTrue(saved)
            assertEquals(setOf("설탕", "생강"), fridge.ingredients.map { it.name }.toSet())
        }
    }

    @Test fun backCannotLeaveTheEditorDuringAnUnfinishedSave() {
        val gate = CompletableDeferred<Unit>()
        val repository = object : FridgeRepository {
            override val names = MutableStateFlow(listOf("소금"))
            override suspend fun add(values: List<String>) = Unit
            override suspend fun remove(value: String) = Unit
            override suspend fun replaceSelection(options: Set<String>, selected: List<String>) {
                gate.await()
                names.value = selected
            }
        }
        val fridge = FridgeViewModel(repository)
        var backCount = 0
        var savedCount = 0
        rule.setContent { MaterialTheme { EditPantryScreen(fridge, { backCount++ }, { savedCount++ }) } }
        try {
            rule.onNodeWithText("저장").performClick()
            rule.onNodeWithContentDescription("back").performClick()
            rule.runOnIdle {
                assertTrue(fridge.isSavingPantry)
                assertEquals(0, backCount)
                assertEquals(0, savedCount)
            }
            gate.complete(Unit)
            rule.waitUntil { savedCount == 1 }
        } finally { gate.complete(Unit) }
    }

    @Test fun entryCompletionSelectsTheCatalogName() {
        val editor = IngredientEditorState().apply { startAdd() }
        rule.setContent { MaterialTheme { EditableIngredientList(editor, listOf("양파", "양배추", "두부")) } }
        rule.onNode(hasSetTextAction()).performTextInput("양")
        rule.onNodeWithText("양파").assertIsDisplayed().performClick()
        rule.runOnIdle {
            assertEquals(listOf(Ingredient("양파")), editor.ingredients.toList())
            assertNull(editor.editingIndex)
        }
    }

    @Test fun fridgeRecommendationButtonUsesCurrentInventory() {
        var sent = emptyList<String>()
        val api = object : IngredientSupportApi {
            override suspend fun ingredientNames() = IngredientCatalogResponse(listOf("두부"))
            override suspend fun ingredientSuggestions(request: IngredientSuggestionRequest): IngredientSuggestionResponse {
                sent = request.ingredients
                return IngredientSuggestionResponse(listOf(IngredientSuggestionDto("계란", 2, 10, listOf("계란밥"))))
            }
            override suspend fun analyze(image: MultipartBody.Part): AnalyzeResponse = error("Not used")
            override suspend fun recommend(request: RecommendRequest): RecommendResponse = error("Not used")
        }
        val fridge = FridgeViewModel().apply { addIngredients(listOf(Ingredient("두부"))) }
        val user = UserViewModel()
        val suggestions = IngredientSuggestionViewModel(api)
        rule.setContent { MaterialTheme { FridgeScreen(user, fridge, {}, ingredientSuggestions = suggestions) } }
        rule.onNodeWithText("추천").performClick()
        rule.onNodeWithText("식재료 추천").assertIsDisplayed()
        rule.onNodeWithText("추가하면 바로 만들 수 있는 요리 2개").assertIsDisplayed()
        rule.onNodeWithText("이 재료가 들어가는 전체 레시피 10개").assertIsDisplayed()
        rule.runOnIdle { assertEquals(listOf("두부"), sent) }
    }
}
