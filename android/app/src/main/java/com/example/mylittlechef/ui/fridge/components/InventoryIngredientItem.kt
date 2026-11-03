// Multi-selection semantics assisted by Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui.fridge.components

import androidx.compose.foundation.combinedClickable
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
    Box(
        Modifier.fillMaxWidth().heightIn(min = 76.dp)
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
        IngredientItem(ingredient, appearance = appearance)
        if (managing) {
            Checkbox(
                checked = selected,
                onCheckedChange = null,
                enabled = enabled,
                modifier = Modifier.align(Alignment.TopEnd).size(24.dp)
            )
        }
    }
}
