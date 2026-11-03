// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui.recipe

import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.model.*
import com.example.mylittlechef.viewmodel.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class RecipeCardInteractionTest {
    @get:Rule val rule=createComposeRule()

    @Test fun cardImageTitleAndBodyOpenDetailsButFavoriteDoesNot() {
        var opened=0
        val user=UserViewModel(); val fridge=FridgeViewModel()
        val recipe=Recipe(7,"카드 테스트",10,1,listOf(Ingredient("두부")),listOf("조리"),missing=emptyList())
        rule.setContent { MaterialTheme { RecipeCard(user,fridge,recipe,{opened++},{}) } }
        rule.onNodeWithText("카드 테스트",useUnmergedTree=true).performTouchInput { click() }
        rule.runOnIdle { assertEquals(1,opened) }
        rule.onNodeWithText("지금 바로 만들 수 있어요",useUnmergedTree=true).performTouchInput { click() }
        rule.runOnIdle { assertEquals(2,opened) }
        rule.onNodeWithTag("recipe-image-7",useUnmergedTree=true).performTouchInput {
            click(bottomRight-androidx.compose.ui.geometry.Offset(10.dp.toPx(),10.dp.toPx()))
        }
        rule.runOnIdle { assertEquals(3,opened) }
        rule.onNodeWithContentDescription("즐겨찾기 추가").performTouchInput { click() }
        rule.runOnIdle { assertEquals(3,opened); assertEquals(listOf(7L),user.likes) }
    }
}
