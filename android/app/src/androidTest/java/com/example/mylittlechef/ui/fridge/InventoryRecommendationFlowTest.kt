package com.example.mylittlechef.ui.fridge

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.longClick
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performTouchInput
import com.example.mylittlechef.data.remote.AnalyzeResponse
import com.example.mylittlechef.data.remote.MyLittleChefApi
import com.example.mylittlechef.data.remote.RecipeDto
import com.example.mylittlechef.data.remote.RecommendRequest
import com.example.mylittlechef.data.remote.RecommendResponse
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.navigation.MainScreen
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.RecipeViewModel
import com.example.mylittlechef.viewmodel.UserViewModel
import okhttp3.MultipartBody
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

class InventoryRecommendationFlowTest {
    @get:Rule val composeRule = createComposeRule()

    @Test fun returningToRecipesUsesTheInventoryAfterDeletion() {
        val requests = mutableListOf<List<String>>()
        val api = object : MyLittleChefApi {
            override suspend fun analyze(image: MultipartBody.Part): AnalyzeResponse = error("Not used")
            override suspend fun recommend(request: RecommendRequest): RecommendResponse {
                requests += request.ingredients
                val hasTofu = "두부" in request.ingredients
                return RecommendResponse(emptyList(), listOf(RecipeDto(
                    if (hasTofu) 11 else 12, if (hasTofu) "두부 요리" else "계란 요리",
                    10, 1, request.ingredients, listOf("조리하기"), emptyList())))
            }
        }
        val fridge = FridgeViewModel().apply {
            addIngredients(listOf(Ingredient("두부"), Ingredient("계란")))
        }
        val recipes = RecipeViewModel(api)
        val user = UserViewModel(nickname = "테스트")
        composeRule.setContent {
            MaterialTheme {
                MainScreen(user, fridge, recipes,
                    {}, {}, {}, {}, {})
            }
        }
        composeRule.onNodeWithText("레시피").performClick()
        composeRule.onNodeWithText("두부 요리").assertIsDisplayed()
        composeRule.onNodeWithText("냉장고").performClick()
        composeRule.onNodeWithTag("fridge-ingredient-두부").performTouchInput { longClick() }
        composeRule.onNodeWithTag("confirm-ingredient-delete").performClick()
        composeRule.onNodeWithText("레시피").performClick()
        composeRule.onNodeWithText("계란 요리").assertIsDisplayed()
        composeRule.runOnIdle { assertEquals(listOf("계란"), requests.last()) }
    }
}
