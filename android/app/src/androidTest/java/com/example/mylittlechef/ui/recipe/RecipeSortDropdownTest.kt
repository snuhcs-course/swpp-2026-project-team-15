// Ported with Claude Code (Opus 5.5), 2026-11-20, from the #24 RecipeSortDropdownTest to the dish sorts
// (the server has no cooking time, so that sort is gone).
package com.example.mylittlechef.ui.recipe

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.assertTextContains
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithTag
import androidx.compose.ui.test.performClick
import com.example.mylittlechef.domain.DishSort
import org.junit.Rule
import org.junit.Test

class RecipeSortDropdownTest {
    @get:Rule val composeRule = createComposeRule()

    @Test fun opensAndSelectsName() {
        var selected by mutableStateOf(DishSort.FEWEST_MISSING)
        composeRule.setContent { RecipeSortDropdown(selected = selected, onSelected = { selected = it }) }
        composeRule.onNodeWithTag("recipe-sort-trigger").performClick()
        composeRule.onNodeWithTag("recipe-sort-NAME").assertIsDisplayed().performClick()
        composeRule.onNodeWithTag("recipe-sort-trigger").assertTextContains("정렬: 이름순 ⌄")
    }

    @Test fun canReturnToFewestMissing() {
        var selected by mutableStateOf(DishSort.NAME)
        composeRule.setContent { RecipeSortDropdown(selected = selected, onSelected = { selected = it }) }
        composeRule.onNodeWithTag("recipe-sort-trigger").performClick()
        composeRule.onNodeWithTag("recipe-sort-FEWEST_MISSING").assertIsDisplayed().performClick()
        composeRule.onNodeWithTag("recipe-sort-trigger").assertTextContains("정렬: 부족한 재료 적은 순 ⌄")
    }
}
