package com.example.mylittlechef.ui.fridge.components

import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.size
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.ui.graphics.Color
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.R
import com.example.mylittlechef.model.Ingredient

@Composable
fun InventoryIngredientItem(
    ingredient: Ingredient,
    managing: Boolean,
    enabled: Boolean,
    onRemoveRequest: () -> Unit
) {
    Box(
        Modifier.fillMaxWidth().heightIn(min = 76.dp)
            .testTag("fridge-ingredient-" + ingredient.name)
            .combinedClickable(
                enabled = enabled,
                onClick = { if (managing) onRemoveRequest() },
                onLongClickLabel = ingredient.name + " 삭제",
                onLongClick = onRemoveRequest
            ),
        contentAlignment = Alignment.Center
    ) {
        IngredientItem(ingredient)
        if (managing) {
            IconButton(
                onClick = onRemoveRequest,
                enabled = enabled,
                modifier = Modifier.align(Alignment.TopEnd).size(48.dp)
                    .testTag("fridge-delete-" + ingredient.name)
            ) {
                Icon(
                    painterResource(R.drawable.ic_remove),
                    contentDescription = ingredient.name + " 삭제",
                    tint = Color.Unspecified,
                    modifier = Modifier.size(22.dp)
                )
            }
        }
    }
}
