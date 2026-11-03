// AI-generated initial fridge-layout scaffold with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
package com.example.mylittlechef.ui.fridge.components

import androidx.compose.foundation.layout.*
import androidx.compose.material3.HorizontalDivider
import androidx.compose.runtime.Composable
import androidx.compose.runtime.key
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.model.Ingredient

@Composable
fun FridgeShelves(
    ingredients: List<Ingredient>,
    modifier: Modifier = Modifier,
    columns: Int = 4,
    minShelves: Int = 5,
    shelfHeight: Dp = 90.dp,
    lineColor: Color = Color.Black,
    managing: Boolean = false,
    controlsEnabled: Boolean = true,
    onRemoveIngredient: (String) -> Unit = {}
) {
    val rows = ingredients.chunked(columns)
    val extraShelf = if (ingredients.size % columns == 0) 1 else 0
    val shelfCount = maxOf(rows.size + extraShelf, minShelves)

    Column(modifier) {
        repeat(shelfCount) { index ->
            val rowItems = rows.getOrNull(index).orEmpty()
            Row(
                Modifier.fillMaxWidth().height(shelfHeight),
                verticalAlignment = Alignment.CenterVertically
            ) {
                repeat(columns) { col ->
                    Box(Modifier.weight(1f), contentAlignment = Alignment.Center) {
                        rowItems.getOrNull(col)?.let { ingredient ->
                            key(ingredient.name) {
                                InventoryIngredientItem(
                                    ingredient = ingredient,
                                    managing = managing,
                                    enabled = controlsEnabled,
                                    onRemoveRequest = { onRemoveIngredient(ingredient.name) }
                                )
                            }
                        }
                    }
                }
            }
            HorizontalDivider(thickness = 1.dp, color = lineColor)
        }
    }
}
