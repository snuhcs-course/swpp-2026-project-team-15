package com.example.mylittlechef.integration

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.data.recipes.NetworkRecipeSource
import com.example.mylittlechef.data.remote.ApiClient
import com.example.mylittlechef.domain.FridgeInventory
import com.example.mylittlechef.ui.recipe.IntegratedRecipeDetail
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

/**
 * US02/03/04/05 chained device/network/render scenario.
 * Requires the documented 560-item local DB, both providers=mock and adb reverse8000.
 * Confirmation is an explicit scripted user choice; no real AI or safety oracle.
 */
class IntegratedBackendFlowTest {
    @get:Rule val compose = createComposeRule()

    @Test fun reviewedPhotoToVersionedRecommendationAndOriginalDetail() {
        val recipe = runBlocking {
            val photo = MultipartBody.Part.createFormData("image", "fixture.jpg",
                "mock device photo".toByteArray().toRequestBody("image/jpeg".toMediaType()))
            val candidates = ApiClient.api.analyze(photo).candidates
            assertTrue(candidates.isNotEmpty())
            val beforeConfirmation = FridgeInventory()
            assertTrue(beforeConfirmation.names.isEmpty())
            // User corrects recognition and adds confirmed names, rather than saving raw candidates.
            val confirmed = beforeConfirmation.addAll(listOf("계란", "김치", "밥"))
            val result = NetworkRecipeSource().recommend(confirmed.names)
            assertTrue(result.unmapped.isEmpty())
            assertTrue(result.recipes.isNotEmpty())
            val first = result.recipes.first()
            assertTrue(first.revision!!.reason.contains("MOCK ONLY"))
            first
        }
        compose.setContent { IntegratedRecipeDetail(recipe) }
        compose.onNodeWithTag("recipe-version").assertTextEquals("원본 레시피")
        compose.onNodeWithTag("revision-status").assertTextContains("AI 수정 거절", substring = true)
    }
}
