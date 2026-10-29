package com.example.mylittlechef.integration

import android.graphics.Bitmap
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mylittlechef.BuildConfig
import com.example.mylittlechef.data.remote.ApiClient
import com.example.mylittlechef.data.remote.IngredientSuggestionRequest
import com.example.mylittlechef.data.remote.RecommendRequest
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.ByteArrayOutputStream

/** Opt-in loopback test; run only against the locally launched mock vision server. */
class LocalRestorationApiTest {
    @Test fun localCatalogSuggestionsRecipesAndPhotoRoundTrip() = runBlocking {
        assumeTrue(InstrumentationRegistry.getArguments().getString("localMock") == "true")
        assertEquals("http://127.0.0.1:8000/", BuildConfig.SERVER_BASE_URL)
        val api = ApiClient.api
        val catalog = api.ingredientNames().names
        assertTrue(catalog.containsAll(listOf("양파", "두부", "계란")))
        val inventory = listOf("밥", "두부", "계란", "김치", "대파")
        val suggestions = api.ingredientSuggestions(IngredientSuggestionRequest(inventory)).suggestions
        assertTrue(suggestions.isNotEmpty())
        assertTrue(suggestions.none { it.name in inventory })
        val expected = suggestions.sortedWith(compareByDescending<com.example.mylittlechef.data.remote.IngredientSuggestionDto> {
            it.readyRecipeCount
        }.thenByDescending { it.recipeCount }.thenBy { it.name })
        assertEquals(expected, suggestions)
        val recipes = api.recommend(RecommendRequest(inventory)).recipes
        assertTrue(recipes.isNotEmpty())
        assertTrue(recipes.all { it.name.isNotBlank() && it.steps.isNotEmpty() })
        val bytes = ByteArrayOutputStream().use { out ->
            Bitmap.createBitmap(8, 8, Bitmap.Config.ARGB_8888).apply {
                eraseColor(android.graphics.Color.WHITE)
                compress(Bitmap.CompressFormat.JPEG, 90, out)
                recycle()
            }
            out.toByteArray()
        }
        val photo = MultipartBody.Part.createFormData("image", "mock-test.jpg",
            bytes.toRequestBody("image/jpeg".toMediaType()))
        val candidates = api.analyze(photo).candidates
        assertTrue(candidates.isNotEmpty())
        assertTrue(candidates.all { it.name.isNotBlank() })
    }
}
