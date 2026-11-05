// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.integration

import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mylittlechef.BuildConfig
import com.example.mylittlechef.data.local.IngredientPresentationProvider
import com.example.mylittlechef.data.remote.ApiClient
import com.example.mylittlechef.data.remote.RecommendRequest
import kotlinx.coroutines.runBlocking
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.ui.recipe.RecipeScreen
import com.example.mylittlechef.ui.theme.MyLittleChefTheme
import com.example.mylittlechef.viewmodel.*
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Rule
import org.junit.Test

/** Opt-in actual deployed list only. Does not call analyze or the paid revision endpoint. */
class CloudRecipeListTest {
    @get:Rule val rule = createComposeRule()

    @Test fun phoneDisplaysRecipesFromCurrentMainWithoutLocalEndpointsOrAiCalls() {
        assumeTrue(InstrumentationRegistry.getArguments().getString("cloudList") == "true")
        assertEquals("http://158.101.141.165/",BuildConfig.SERVER_BASE_URL)
        assertTrue(BuildConfig.APPLICATION_ID.endsWith(".cloudtest"))
        assertTrue("Cloud Test must permit the configured HTTP host",
            android.security.NetworkSecurityPolicy.getInstance().isCleartextTrafficPermitted("158.101.141.165"))
        // Surface transport/decoding failures directly, before the ViewModel's friendly message.
        val probe=runBlocking { ApiClient.api.recommend(RecommendRequest(listOf("밥","두부","계란","김치","대파"))) }
        assertTrue(probe.recipes.isNotEmpty())
        val context=InstrumentationRegistry.getInstrumentation().targetContext
        val ids=IngredientPresentationProvider.get(context).ingredientIds
        val vm=RecipeViewModel(ApiClient.api,ids)
        val fridge=FridgeViewModel().apply {
            addIngredients(listOf("밥","두부","계란","김치","대파").map(::Ingredient))
        }
        val user=UserViewModel(nickname="서버 확인")
        rule.setContent { MyLittleChefTheme { RecipeScreen(user,fridge,vm,{},{}) } }
        rule.waitUntil(40_000) { !vm.isLoading && (vm.error != null || vm.recommended.isNotEmpty()) }
        rule.runOnIdle {
            assertNull(vm.error)
            assertTrue(vm.recommended.isNotEmpty())
            assertTrue(vm.recommended.all { it.steps.isNotEmpty() && it.name.isNotBlank() })
            assertNull(vm.batchRevisionMessage)
            assertFalse(vm.batchRevisionLoading)
        }
        rule.onNodeWithText(vm.recommended.first().name).assertIsDisplayed()
        rule.onNodeWithText("AI 레시피 제안 받기").assertIsDisplayed()
        context.cacheDir.resolve("cloud-list-verification.txt").writeText(
            "endpoint=${BuildConfig.SERVER_BASE_URL}\ncount=${vm.recommended.size}\nfirst=${vm.recommended.first().name}\nrevision_request=false\n")
    }
}
