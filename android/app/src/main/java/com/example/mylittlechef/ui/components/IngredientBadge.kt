// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.data.local.IngredientPresentationProvider
import com.example.mylittlechef.ui.fridge.components.ingredientIconResource

/** The fixed pastel disc and dark line art preserve catalog identity in both themes. */
@Composable
fun IngredientBadge(name: String, modifier: Modifier = Modifier, size: Dp = 32.dp) {
    val context = LocalContext.current
    val catalog = remember(context) { IngredientPresentationProvider.get(context) }
    val appearance = catalog.appearanceFor(name)
    Box(modifier.size(size).clip(CircleShape).background(Color(appearance.backgroundArgb)),
        contentAlignment = Alignment.Center) {
        Icon(painterResource(ingredientIconResource(appearance.iconKey)), contentDescription = name,
            tint = Color(0xFF172C25), modifier = Modifier.size(size))
    }
}
