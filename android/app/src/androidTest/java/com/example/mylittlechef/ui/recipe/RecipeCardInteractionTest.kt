// Ported with Claude Code (Opus 5.5), 2026-11-20, from the #24 RecipeCardInteractionTest to the dish cards.
package com.example.mylittlechef.ui.recipe

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.data.remote.DishApi
import com.example.mylittlechef.data.remote.DishCatalogResponse
import com.example.mylittlechef.data.remote.DishDto
import com.example.mylittlechef.data.remote.DishSuggestRequest
import com.example.mylittlechef.data.remote.DishSuggestResponse
import com.example.mylittlechef.data.remote.DishVideosRequest
import com.example.mylittlechef.data.remote.DishVideosResponse
import com.example.mylittlechef.domain.Dish
import com.example.mylittlechef.viewmodel.DishViewModel
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class RecipeCardInteractionTest {
    @get:Rule val rule = createComposeRule()

    private object Api : DishApi {
        override suspend fun dishes() = DishCatalogResponse(emptyList(), 0)
        override suspend fun suggest(request: DishSuggestRequest) = DishSuggestResponse("llm", listOf(
            DishDto("tofu", "카드 테스트", "반찬", listOf("두부"), emptyList(), "", emptyList(), null)))
        override suspend fun videos(request: DishVideosRequest) = DishVideosResponse(emptyList())
    }

    @Test fun cardImageTitleAndBodyOpenDetailsButFavoriteDoesNot() {
        var opened = 0
        val vm = DishViewModel(Api, debounceMillis = 0)
        vm.onFridgeChanged(listOf("두부"))
        rule.waitUntil(5_000) { vm.visibleSuggestions("").isNotEmpty() }
        val dish: Dish = vm.visibleSuggestions("").single()
        rule.setContent { MaterialTheme { RecipeCard(vm, dish) { opened++ } } }
        rule.onNodeWithText("카드 테스트", useUnmergedTree = true).performTouchInput { click() }
        rule.runOnIdle { assertEquals(1, opened) }
        rule.onNodeWithText("핵심 재료가 다 있어요", useUnmergedTree = true).performTouchInput { click() }
        rule.runOnIdle { assertEquals(2, opened) }
        rule.onNodeWithTag("recipe-image-tofu", useUnmergedTree = true).performTouchInput {
            click(bottomRight - androidx.compose.ui.geometry.Offset(10.dp.toPx(), 10.dp.toPx()))
        }
        rule.runOnIdle { assertEquals(3, opened) }
        rule.onNodeWithContentDescription("즐겨찾기 추가").performTouchInput { click() }
        rule.waitUntil(5_000) { vm.isFavorite("tofu") }
        rule.runOnIdle { assertEquals(3, opened) }
    }
}
