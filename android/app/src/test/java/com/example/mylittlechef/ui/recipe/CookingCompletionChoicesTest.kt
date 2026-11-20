// AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.ui.recipe

import com.example.mylittlechef.domain.Availability
import com.example.mylittlechef.domain.DishRecipe
import com.example.mylittlechef.domain.RecipeIngredient
import com.example.mylittlechef.domain.RecipeStep
import org.junit.Assert.assertEquals
import org.junit.Test

class CookingCompletionChoicesTest {
    private fun recipe(vararg rows: Pair<String, Availability>) = DishRecipe(
        dishId = "d", name = "d", videoTitle = null, videoChannel = null, servings = 1,
        ingredients = rows.map { RecipeIngredient(it.first, null, it.second) },
        steps = listOf(RecipeStep(1, "x")), tips = emptyList(), uncertain = emptyList(), captionGaps = false
    )

    // 요리 완료 removes only what the user ticks: same-name owned rows start ticked, a related name
    // (청양고추 for a 고추 row) is offered unticked, staples and missing rows are not offered.
    @Test fun exactOwnedRowsStartTickedAndRelatedNamesAreOfferedUnticked() {
        val (choices, ticked) = usedFridgeItems(
            recipe("계란" to Availability.OWNED, "고추" to Availability.OWNED, "소금" to Availability.ASSUMED, "대파" to Availability.UNAVAILABLE),
            listOf("계란", "청양고추", "소금", "우유")
        )
        assertEquals(listOf("계란", "청양고추"), choices)
        assertEquals(setOf("계란"), ticked)
    }
}
