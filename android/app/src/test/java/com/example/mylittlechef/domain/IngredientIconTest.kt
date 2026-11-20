// AI-generated with Claude Code (Opus 5.5), 2026-11-19; not yet reviewed.
package com.example.mylittlechef.domain

import com.example.mylittlechef.R
import com.example.mylittlechef.ui.fridge.components.ingredientIconResource
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test
import java.io.File

class IngredientIconTest {
    // Phone test 2026-11-19: 감자 showed the carrot icon.
    @Test fun potatoHasItsOwnIcon() {
        val shipped = IngredientPresentationCatalog.fromCsv(File("src/main/assets/ingredient_presentation.csv").readText())
        assertEquals("potato", shipped.appearanceFor("감자").iconKey)
        assertEquals("root", shipped.appearanceFor("당근").iconKey)
    }

    @Test fun everyIconKeyHasItsOwnDrawable() {
        for (key in IngredientPresentationCatalog.iconKeys - "generic") {
            assertNotEquals(key, R.drawable.ic_ingredient_generic, ingredientIconResource(key))
        }
    }
}
