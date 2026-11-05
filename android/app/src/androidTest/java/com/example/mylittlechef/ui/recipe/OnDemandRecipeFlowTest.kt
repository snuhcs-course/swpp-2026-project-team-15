package com.example.mylittlechef.ui.recipe

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.model.*
import com.example.mylittlechef.viewmodel.*
import okhttp3.MultipartBody
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class OnDemandRecipeFlowTest {
    @get:Rule val rule = createComposeRule()
    private class Fake : MyLittleChefApi, OnDemandRecipeApi {
        var calls = 0
        val source = SourceRecipeDto(7,"Original","10분","2인분",
            listOf(SourceIngredientDto(1,"계란","2개"),SourceIngredientDto(2,"양파","1개")),listOf(SourceStepDto(1,"Original step")))
        override suspend fun recipeCatalog() = RecipeCatalogDto(listOf(CatalogItemDto(1,"계란",listOf("계란"))))
        override suspend fun candidates(request: InventoryIdsDto) = CandidatesDto(listOf(CandidateDto(7,source,listOf(source.ingredients[1]),true)))
        override suspend fun reviseRecipe(id: Long, request: InventoryIdsDto): SingleRevisionDto {
            calls++
            return SingleRevisionDto(7,source,RevisionOutcomeDto("revised",RevisionResultDto("",listOf(RevisionChangeDto("omission","Skip onion")),
                RevisedRecipeDto("Adjusted","1인분",listOf(source.ingredients[0]),listOf(SourceStepDto(1,"Revised step")))),null))
        }
        override suspend fun analyze(image: MultipartBody.Part): AnalyzeResponse = error("Not used")
        override suspend fun recommend(request: RecommendRequest): RecommendResponse = error("Legacy API must not be called")
    }
    @Test fun originalFirstExplicitRequestToggleAndRevisit() {
        val api = Fake(); val vm = RecipeViewModel(api)
        val fridge = FridgeViewModel().apply { addIngredients(listOf(Ingredient("계란"))) }
        val user = UserViewModel(nickname="테스트")
        var selected by mutableStateOf<Recipe?>(null)
        rule.setContent {
            MaterialTheme {
                if (selected == null) RecipeScreen(user,fridge,vm,{selected=it},{})
                else RecipeDetailScreen(user,selected!!,{selected=null},{},vm.revisionState(7),{vm.requestRevision(7)})
            }
        }
        rule.waitUntil { vm.recommended.isNotEmpty() }
        rule.onNodeWithText("✦ AI 조정 후보").assertIsDisplayed()
        rule.runOnIdle { assertEquals(0,api.calls) }
        rule.onNodeWithContentDescription("more").performClick()
        rule.onNodeWithText("1. Original step").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("AI 제안 보기").performScrollTo().performClick()
        rule.onNodeWithText("1. Revised step").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("원본 보기").performScrollTo().performClick()
        rule.onNodeWithText("1. Original step").performScrollTo().assertIsDisplayed()
        rule.onNodeWithContentDescription("back").performClick()
        rule.waitUntil { vm.recommended.isNotEmpty() }
        rule.onNodeWithContentDescription("more").performClick()
        rule.onNodeWithText("1. Original step").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("AI 제안 보기").performScrollTo().performClick()
        rule.onNodeWithText("1. Revised step").performScrollTo().assertIsDisplayed()
        rule.runOnIdle { assertEquals(1,api.calls) }
    }
}
