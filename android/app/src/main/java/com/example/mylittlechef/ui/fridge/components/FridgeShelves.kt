// UAT stage 2 assisted by Codex, 2026-11-24; human review pending.
// UX2 layout/lifecycle changes assisted by Codex, 2026-11-19; human review pending.
// Photo-led tiles assisted by Codex, 2026-11-19; human review pending.
// Atomic multi-selection deletion assisted by Codex, 2026-11-03; human review pending.
// Fridge presentation/sorting and arrival-order updates assisted by Codex, 2026-11-02; human review pending.
// AI-generated initial fridge-layout scaffold with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
package com.example.mylittlechef.ui.fridge.components

import com.example.mylittlechef.ui.components.DragSelectionGroup
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
    onLongPressIngredient: (String) -> Unit = onRemoveIngredient,
    onSelectionChange: (Set<String>) -> Unit = {},
    onIngredientClick: (String) -> Unit = {}
) {
    val groups = mapOf(null to ingredients)

    DragSelectionGroup(selectedNames, onSelectionChange, modifier, enabled=controlsEnabled, onStart=onLongPressIngredient) {
    Column {
        groups.forEach { (category, groupItems) ->
            val rows = groupItems.chunked(columns)
            val shelfCount = rows.size
            repeat(shelfCount) { index ->
                val rowItems = rows.getOrNull(index).orEmpty()
                Row(
                    Modifier.fillMaxWidth().heightIn(min = 80.dp).padding(bottom = 2.dp),
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
                                        onIngredientClick = { onIngredientClick(ingredient.name) },
                                        selected = ingredient.name in selectedNames,
                                        appearance = catalog?.appearanceFor(ingredient.name)
                                    )
                                }
                            }
                        }
                    }
                }

            }
        }
    }
    }
}
