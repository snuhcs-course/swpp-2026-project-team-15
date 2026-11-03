// Atomic multi-selection deletion assisted by Codex, 2026-11-03; human review pending.
// Fridge presentation/sorting and arrival-order updates assisted by Codex, 2026-11-02; human review pending.
// AI-generated initial fridge-layout scaffold with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
package com.example.mylittlechef.ui.fridge.components

import androidx.compose.foundation.layout.*
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.key
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.platform.testTag
import com.example.mylittlechef.domain.IngredientPresentationCatalog
import com.example.mylittlechef.model.Ingredient

@Composable
fun FridgeShelves(
    ingredients: List<Ingredient>,
    modifier: Modifier = Modifier,
    columns: Int = 4,
    minShelves: Int = 5,
    shelfHeight: Dp = 90.dp,
    lineColor: Color = MaterialTheme.colorScheme.outlineVariant,
    managing: Boolean = false,
    controlsEnabled: Boolean = true,
    onRemoveIngredient: (String) -> Unit = {},
    catalog: IngredientPresentationCatalog? = null,
    groupedByCategory: Boolean = false,
    selectedNames: Set<String> = emptySet(),
    onLongPressIngredient: (String) -> Unit = onRemoveIngredient
) {
    val groups = if (groupedByCategory && catalog != null && ingredients.isNotEmpty())
        ingredients.groupBy { catalog.appearanceFor(it.name).category }
    else mapOf(null to ingredients)

    Column(modifier) {
        groups.forEach { (category, groupItems) ->
            if (category != null) {
                Text(
                    category.label,
                    style = MaterialTheme.typography.labelMedium,
                    modifier = Modifier.padding(top = 12.dp, bottom = 2.dp)
                        .testTag("fridge-category-" + category.key)
                )
            }
            val rows = groupItems.chunked(columns)
            val shelfCount = if (category != null) rows.size else
                maxOf(rows.size + if (groupItems.size % columns == 0) 1 else 0, minShelves)
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
                                        onRemoveRequest = { onRemoveIngredient(ingredient.name) },
                                        onLongPress = { onLongPressIngredient(ingredient.name) },
                                        selected = ingredient.name in selectedNames,
                                        appearance = catalog?.appearanceFor(ingredient.name)
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
}
