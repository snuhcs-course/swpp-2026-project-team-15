package com.example.mylittlechef.integration

import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import com.example.mylittlechef.data.remote.ApiClient
import com.example.mylittlechef.data.remote.RecommendRequest
import com.example.mylittlechef.data.remote.toRecipe
import com.example.mylittlechef.domain.FridgeInventory
import com.example.mylittlechef.ui.recipe.RecipeDetailScreen
import com.example.mylittlechef.viewmodel.UserViewModel
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

/** Original photo/name API and detail rendering; requires a mock server and matching DB. */
class IntegratedBackendFlowTest {
    @get:Rule val compose = createComposeRule()

    @Test fun reviewedPhotoToOriginalRecommendationAndDetail() {
        val recipe = runBlocking {
            val photo = MultipartBody.Part.createFormData("image", "fixture.jpg",
                "mock device photo".toByteArray().toRequestBody("image/jpeg".toMediaType()))
            assertTrue(ApiClient.api.analyze(photo).candidates.isNotEmpty())
            val beforeConfirmation = FridgeInventory()
            assertTrue(beforeConfirmation.names.isEmpty())
            val confirmed = beforeConfirmation.addAll(listOf("계란", "김치", "밥"))
            val result = ApiClient.api.recommend(RecommendRequest(confirmed.names)).recipes
            assertTrue(result.isNotEmpty())
            result.first().toRecipe()
        }
        val user = UserViewModel()
        compose.setContent {
            RecipeDetailScreen(user, recipe, onBackClick = {}, onLikeClick = {})
        }
        compose.onNodeWithText(recipe.name).assertExists()
    }
}
