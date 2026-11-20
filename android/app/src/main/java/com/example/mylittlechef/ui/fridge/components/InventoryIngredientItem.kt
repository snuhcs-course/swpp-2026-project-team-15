// UX2 layout/lifecycle changes assisted by Codex, 2026-11-19; human review pending.
// Photo-led selection motion assisted by Codex, 2026-11-19; human review pending.
// Multi-selection semantics assisted by Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui.fridge.components

import androidx.compose.foundation.combinedClickable
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.border
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.graphics.Color
import androidx.compose.material3.MaterialTheme
import androidx.compose.ui.draw.clip
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.height
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Checkbox
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.domain.IngredientAppearance
import com.example.mylittlechef.model.Ingredient

@Composable
fun InventoryIngredientItem(
    ingredient: Ingredient,
    managing: Boolean,
    enabled: Boolean,
    onRemoveRequest: () -> Unit,
    appearance: IngredientAppearance? = null,
    selected: Boolean = false,
    onLongPress: () -> Unit = onRemoveRequest
) {
    val outline = animateColorAsState(if(selected && managing) MaterialTheme.colorScheme.primary else Color.Transparent, tween(160), label="ingredient-selection").value
    Box(
        Modifier.fillMaxWidth().heightIn(min = 80.dp).clip(RoundedCornerShape(18.dp))
            .border(1.5.dp, outline, RoundedCornerShape(18.dp)).padding(vertical = 4.dp)
            .testTag("fridge-ingredient-" + ingredient.name)
            .semantics { if (managing) this.selected = selected }
            .combinedClickable(
                enabled = enabled,
                role = if (managing) Role.Checkbox else Role.Button,
                onClickLabel = if (managing) ingredient.name + " 선택 전환" else null,
                onClick = { if (managing) onRemoveRequest() },
                onLongClickLabel = ingredient.name + " 선택",
                onLongClick = onLongPress
            ),
        contentAlignment = Alignment.Center
    ) {
        IngredientItem(ingredient, imageSize = 48.dp, appearance = appearance)
        androidx.compose.animation.AnimatedVisibility(visible=managing, enter=fadeIn(tween(140)), exit=fadeOut(tween(100)), modifier=Modifier.align(Alignment.TopEnd)) {
            Checkbox(
                checked = selected,
                onCheckedChange = null,
                enabled = enabled,
                modifier = Modifier.size(24.dp)
            )
        }
    }
}
