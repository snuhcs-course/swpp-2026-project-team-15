package com.example.mylittlechef.ui.recipe

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import com.example.mylittlechef.domain.RecipeSortType
import org.junit.Rule
import org.junit.Test

class RecipeSortDropdownTest {
    @get:Rule val composeRule = createComposeRule()

    @Test fun opensAndSelectsCookingTime() {
        var selected by mutableStateOf(RecipeSortType.RECOMMENDED)
        composeRule.setContent {
            RecipeSortDropdown(selected = selected, onSelected = { selected = it })
        }
        composeRule.onNodeWithTag("recipe-sort-trigger").performClick()
        composeRule.onNodeWithTag("recipe-sort-COOKING_TIME").assertIsDisplayed().performClick()
        composeRule.onNodeWithTag("recipe-sort-trigger").assertTextContains("정렬: 조리시간 짧은 순 ⌄")
    }

    @Test fun opensAndSelectsFewestMissing() {
        var selected by mutableStateOf(RecipeSortType.RECOMMENDED)
        composeRule.setContent {
            RecipeSortDropdown(selected = selected, onSelected = { selected = it })
        }
        composeRule.onNodeWithTag("recipe-sort-trigger").performClick()
        composeRule.onNodeWithTag("recipe-sort-FEWEST_MISSING").assertIsDisplayed().performClick()
        composeRule.onNodeWithTag("recipe-sort-trigger").assertTextContains("정렬: 부족한 재료 적은 순 ⌄")
    }
}
