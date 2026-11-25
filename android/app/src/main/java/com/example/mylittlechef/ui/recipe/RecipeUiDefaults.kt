// Recipe visual consistency assisted by Codex, 2026-11-24; human review pending.
package com.example.mylittlechef.ui.recipe

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.unit.dp
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.lerp

internal object RecipeUiDefaults {
    val CardShape = RoundedCornerShape(16.dp)
    val ButtonShape = RoundedCornerShape(13.dp)
    val DialogShape = RoundedCornerShape(24.dp)
    val ControlHeight = 52.dp
}

/** Bounded darkening keeps text readable in either theme and is reversible with Previous. */
internal fun cookingCardColor(base: Color, index: Int, count: Int): Color {
    val progress=if(count<=1) 0f else index.coerceIn(0,count-1).toFloat()/(count-1)
    return lerp(base, Color.Black.copy(alpha=base.alpha), progress*.18f)
}
