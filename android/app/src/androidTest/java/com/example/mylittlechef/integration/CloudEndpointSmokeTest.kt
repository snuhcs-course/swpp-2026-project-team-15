package com.example.mylittlechef.integration

import android.graphics.Bitmap
import android.net.Uri
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onAllNodesWithText
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mylittlechef.BuildConfig
import com.example.mylittlechef.data.remote.ApiClient
import com.example.mylittlechef.data.remote.RecommendRequest
import com.example.mylittlechef.data.remote.toRecipe
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import com.example.mylittlechef.ui.fridge.add.AnalyzeScreen
import com.example.mylittlechef.ui.recipe.RecipeDetailScreen
import com.example.mylittlechef.viewmodel.UserViewModel
import com.example.mylittlechef.ui.theme.MyLittleChefTheme
import com.example.mylittlechef.viewmodel.FridgeViewModel
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test
import java.io.File

/** Opt-in paid test. Supply cloud-smoke.jpg in the isolated target app cache first. */
class CloudEndpointSmokeTest {
    @get:Rule val compose = createComposeRule()

    @Test fun reviewedPhotoToLiveCloudRecipe() {
        assumeTrue(InstrumentationRegistry.getArguments().getString("liveCloud") == "true")
        assertEquals("http://158.101.141.165/", BuildConfig.SERVER_BASE_URL)
        val instrumentation = InstrumentationRegistry.getInstrumentation()
        val cache = instrumentation.targetContext.cacheDir
        val photo = File(cache, "cloud-smoke.jpg")
        assertTrue("Provide the private test photo before opting in", photo.isFile)
        val user = UserViewModel()
        val fridge = FridgeViewModel()
        fridge.addIngredients(listOf(Ingredient("김치"), Ingredient("밥")))
        val initial = fridge.ingredients.toList()
        val selected = mutableStateOf<Recipe?>(null)
        var confirmed = false
        compose.setContent {
            MyLittleChefTheme {
                selected.value?.let { RecipeDetailScreen(user, it, onBackClick = {}, onLikeClick = {}) } ?: AnalyzeScreen(
                    fridge = fridge, onBackClick = {}, onManualClick = {}, onRetakeClick = {},
                    onSaveClick = { confirmed = true }, imageUri = Uri.fromFile(photo).toString()
                )
            }
        }
        compose.waitUntil(timeoutMillis = 70_000) {
            compose.onAllNodesWithText("냉장고에 반영").fetchSemanticsNodes().isNotEmpty()
        }
        assertEquals("Recognition must not save before explicit confirmation", initial, fridge.ingredients)
        File(cache, "cloud-candidates.png").outputStream().use {
            instrumentation.uiAutomation.takeScreenshot().compress(Bitmap.CompressFormat.PNG, 100, it)
        }
        compose.onNodeWithText("냉장고에 반영").performClick()
        compose.waitUntil { confirmed }
        assertTrue(fridge.ingredients.size > initial.size)
        val result = runBlocking {
            ApiClient.api.recommend(RecommendRequest(fridge.ingredients.map { it.name }))
                .recipes.map { it.toRecipe() }
        }
        assertTrue(result.isNotEmpty())
        val recipe = result.first()
        compose.runOnIdle { selected.value = recipe }
        compose.onNodeWithText(recipe.name).assertExists()
        File(cache, "cloud-recipe.png").outputStream().use {
            instrumentation.uiAutomation.takeScreenshot().compress(Bitmap.CompressFormat.PNG, 100, it)
        }
        File(cache, "cloud-result.txt").writeText(
            "endpoint=${BuildConfig.SERVER_BASE_URL}\nrecipe=${recipe.id}\n"
        )
    }
}
