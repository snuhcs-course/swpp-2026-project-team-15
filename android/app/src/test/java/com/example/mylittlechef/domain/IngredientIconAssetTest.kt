// AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.domain

import org.junit.Assert.assertEquals
import org.junit.Test
import java.io.File

/** The shipped ingredient table, read as the app reads it. */
class IngredientIconAssetTest {
    private val catalog = IngredientPresentationCatalog.fromCsv(
        File("src/main/assets/ingredient_presentation.csv").readText()
    )

    // Phone recheck (2026-11-19): 청양고추 showed the round tomato-like vegetable icon.
    @Test fun peppersUseThePepperIcon() {
        for (name in listOf("고추", "청양고추", "꽈리고추", "홍고추", "건고추")) {
            assertEquals(name, "chili", catalog.appearanceFor(name).iconKey)
        }
        assertEquals("fruit_vegetable", catalog.appearanceFor("토마토").iconKey)
    }
}
