// AI-assisted HE regressions, 2026-11-10; human review pending. No network calls.
package com.example.mylittlechef.ui.recipe

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import com.example.mylittlechef.viewmodel.*
import okhttp3.MultipartBody
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class HeRecipeExploreUiTest {
    @get:Rule val rule=createComposeRule()
    private val api=object: MyLittleChefApi {
        override suspend fun analyze(image: MultipartBody.Part): AnalyzeResponse = error("No calls")
        override suspend fun recommend(request: RecommendRequest) = RecommendResponse(emptyList(),emptyList())
    }
    @Test fun recipeNameSearchHidesOnlyTheCurrentExplorationAndCanUndo() {
        val source=object: RecipeExploreApi {
            override suspend fun exploreCapabilities()=ExploreCapabilities(true)
            override suspend fun exploreCatalog()=ExploreCatalog(emptyList())
            override suspend fun explore(request:ExploreRequest):ExploreResponse {
                val rows=listOf(RecipeDto(1,"두부구이",10,1,listOf("두부"),listOf("조리"),emptyList()),
                    RecipeDto(2,"김치찌개",20,1,listOf("김치"),listOf("조리"),listOf("김치")))
                return ExploreResponse(rows.filter { it.name.contains(request.query) && it.id !in request.seenIds },false)
            }
        }
        val user=UserViewModel(); user.addLikes(1)
        val fridge=FridgeViewModel(); val vm=RecipeViewModel(api,exploreApi=source)
        rule.setContent { MaterialTheme { RecipeContent(user,fridge,vm,{}, {}) } }
        rule.runOnIdle { vm.refresh(fridge.ingredients) }
        rule.waitUntil(5000) { vm.recommended.size == 2 }
        rule.onNodeWithText("레시피 이름 검색").assertExists()
        rule.onNodeWithText("다른 추천 보기").assertExists()
        rule.onNodeWithTag("recipe-card-1").performTouchInput { swipeLeft() }
        rule.waitUntil(5000) { vm.lastHiddenRecipe == 1L }
        rule.onNodeWithTag("recipe-card-1").assertDoesNotExist()
        rule.runOnIdle { assertEquals(listOf(1L),user.likes) }
        rule.onNodeWithText("실행 취소").performClick()
        rule.onNodeWithTag("recipe-card-1").assertExists()
        rule.onNode(hasSetTextAction()).performTextInput("김치")
        rule.onNodeWithText("검색").performClick()
        rule.waitUntil(5000) { vm.recommended.size == 1 }
        rule.onNodeWithTag("recipe-card-2").assertExists()
        rule.onNodeWithTag("recipe-card-1").assertDoesNotExist()
    }
    @Test fun unknownIngredientRequiresConsentBeforeAiOmissionAndStaysInInventory() {
        val requests=mutableListOf<BatchRevisionRequest>()
        val batch=object: MyLittleChefApi by api, BatchRecipeApi {
            override suspend fun recommendations(request:BatchRevisionRequest):BatchRecommendationsDto {
                requests.add(request)
                return BatchRecommendationsDto(emptyList(),emptyList(),BatchSummaryDto(1,0,0,null))
            }
        }
        val user=UserViewModel(); val fridge=FridgeViewModel()
        fridge.addIngredients(listOf(Ingredient("두부"),Ingredient("미등록")))
        val vm=RecipeViewModel(batch,mapOf("두부" to 1))
        rule.setContent { MaterialTheme { RecipeContent(user,fridge,vm,{}, {}) } }
        rule.runOnIdle { vm.refresh(fridge.ingredients) }
        rule.onNodeWithText("AI 레시피 제안 받기").performClick()
        rule.onNodeWithText("AI에 전달할 재료 확인").assertIsDisplayed()
        rule.runOnIdle { assertTrue(requests.isEmpty()) }
        rule.onNodeWithText("취소").performClick()
        rule.runOnIdle { assertTrue(requests.isEmpty()) }
        rule.onNodeWithText("AI 레시피 제안 받기").performClick()
        rule.onNodeWithText("이 재료 없이 요청").performClick()
        rule.waitUntil(5000) { requests.size == 1 }
        rule.runOnIdle {
            assertEquals(listOf(1),requests.single().ids)
            assertEquals(listOf("두부","미등록"),fridge.ingredients.map { it.name })
        }
    }
    @Test fun cookingCompletionDeletesOnlyExplicitlySelectedOwnedIngredientsAndCanUndo() {
        val user=UserViewModel(); val fridge=FridgeViewModel()
        fridge.addIngredients(listOf(Ingredient("두부"),Ingredient("대파"),Ingredient("우유")))
        val recipe=Recipe(1,"두부 요리",10,1,listOf(Ingredient("두부"),Ingredient("다진파")),listOf("조리"))
        rule.setContent { MaterialTheme { RecipeDetailScreen(user,recipe,{}, {},fridge=fridge) } }
        rule.onNodeWithText("요리 완료").performScrollTo().performClick()
        rule.onNodeWithText("선택한 재료 삭제").assertIsNotEnabled()
        rule.onNodeWithTag("consumed-두부").assertIsOff().performClick().assertIsOn()
        rule.onNodeWithTag("consumed-대파").assertIsOff()
        rule.onNodeWithTag("consumed-우유").assertDoesNotExist()
        rule.onNodeWithText("선택한 재료 삭제").performClick()
        rule.runOnIdle { assertEquals(listOf("대파","우유"),fridge.ingredients.map { it.name }) }
        rule.onNodeWithText("실행 취소").performClick()
        rule.runOnIdle { assertEquals(listOf("두부","대파","우유"),fridge.ingredients.map { it.name }) }
    }
}
