// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui.recipe

import androidx.compose.runtime.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.model.*
import com.example.mylittlechef.viewmodel.*
import okhttp3.MultipartBody
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class CloudBatchRecipeFlowTest {
    @get:Rule val rule=createComposeRule()
    private class Fake: MyLittleChefApi,BatchRecipeApi {
        var calls=0
        override suspend fun analyze(image:MultipartBody.Part):AnalyzeResponse=error("not used")
        override suspend fun recommend(request:RecommendRequest)=RecommendResponse(emptyList(),
            listOf(RecipeDto(291,"김치쌈밥",20,2,listOf("김치","밥"),listOf("원본 조리법"),listOf("소금"))))
        override suspend fun recommendations(request:BatchRevisionRequest):BatchRecommendationsDto {
            calls++
            val original=SourceRecipeDto(291,"김치쌈밥","20분","2인분",
                listOf(SourceIngredientDto(70,"김치","8장"),SourceIngredientDto(223,"밥","2공기")),listOf(SourceStepDto(1,"원본 조리법")))
            return BatchRecommendationsDto(listOf(BatchRecipeEntryDto(291,original,
                RevisionOutcomeDto("revised",RevisionResultDto("양념을 줄였어요",emptyList(),
                    RevisedRecipeDto("제안 김치쌈밥","1인분",original.ingredients,listOf(SourceStepDto(1,"AI 조리법")))),null))),
                emptyList(),BatchSummaryDto(1,1,1,null))
        }
    }
    @Test fun explicitListActionThenCachedDetailToggleWithoutAnotherRequest() {
        val api=Fake(); val vm=RecipeViewModel(api,mapOf("김치" to 70,"밥" to 223))
        val fridge=FridgeViewModel().apply { addIngredients(listOf(Ingredient("김치"),Ingredient("밥"))) }
        val user=UserViewModel(nickname="테스트")
        var selected by mutableStateOf<Recipe?>(null)
        rule.setContent { MaterialTheme {
            if(selected==null) RecipeScreen(user,fridge,vm,{selected=it},{})
            else RecipeDetailScreen(user,vm.find(selected!!.id)!!,{selected=null},{},vm.revisionState(selected!!.id),{},batchRevision=true)
        } }
        rule.waitUntil { vm.recommended.isNotEmpty() }
        rule.runOnIdle { assertEquals(0,api.calls) }
        rule.onNodeWithText("AI 레시피 제안 받기").performClick()
        rule.onNodeWithText("✦ AI 제안 있음").assertIsDisplayed()
        rule.onNodeWithContentDescription("more").performClick()
        rule.onNodeWithText("1. 원본 조리법").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("AI 제안 보기").performScrollTo().performClick()
        rule.onNodeWithText("1. AI 조리법").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("원본 보기").performScrollTo().performClick()
        rule.onNodeWithText("1. 원본 조리법").performScrollTo().assertIsDisplayed()
        rule.onNodeWithContentDescription("back").performClick()
        rule.waitUntil { vm.recommended.isNotEmpty() }
        rule.onNodeWithText("AI 레시피 제안 받기").assertIsEnabled().performClick()
        rule.waitUntil { api.calls==2 }
        rule.onNodeWithText("AI 레시피 제안 받기").assertIsEnabled()
        rule.runOnIdle { assertEquals(2,api.calls) }
    }

    @Test fun listKeepsExplanationBehindInfoAndAiActionNearBottomRight() {
        val api=Fake(); val vm=RecipeViewModel(api,mapOf("김치" to 70,"밥" to 223))
        val fridge=FridgeViewModel().apply { addIngredients(listOf(Ingredient("김치"),Ingredient("밥"))) }
        val user=UserViewModel(nickname="테스트")
        rule.setContent { MaterialTheme { RecipeScreen(user,fridge,vm,{},{}) } }
        rule.waitUntil { vm.recommended.isNotEmpty() }
        rule.onNodeWithText("김치쌈밥").assertIsDisplayed()
        val fab=rule.onNodeWithText("AI 레시피 제안 받기").getUnclippedBoundsInRoot()
        val info=rule.onNodeWithContentDescription("레시피 안내").getUnclippedBoundsInRoot()
        assertTrue(fab.top>info.bottom)
        val rootBounds=rule.onRoot().getUnclippedBoundsInRoot()
        assertTrue((fab.left+fab.right)/2>(rootBounds.left+rootBounds.right)/2)
        rule.onNodeWithText("알레르기·조리도구",substring=true).assertDoesNotExist()
        rule.onNodeWithContentDescription("레시피 안내").performClick()
        rule.onNodeWithText("알레르기·조리도구",substring=true).assertExists()
        rule.onNodeWithText("확인").performClick()
        rule.runOnIdle { assertEquals(0,api.calls) }
    }
}
