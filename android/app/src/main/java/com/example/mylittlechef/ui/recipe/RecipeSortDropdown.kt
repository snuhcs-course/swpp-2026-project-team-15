// AI-assisted with Codex (GPT-6.1 Sol), 2026-10-14; human review pending.
// Restored on the YouTube-based dishes with Claude Code (Opus 5.5), 2026-11-20: the dish sorts.
package com.example.mylittlechef.ui.recipe

import androidx.compose.foundation.layout.Box
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.layout.heightIn
import androidx.compose.ui.unit.dp
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import com.example.mylittlechef.domain.DishSort

@Composable
fun RecipeSortDropdown(
    selected: DishSort,
    onSelected: (DishSort) -> Unit,
    modifier: Modifier = Modifier
) {
    var expanded by remember { mutableStateOf(false) }
    Box(modifier) {
        OutlinedButton(
            onClick = { expanded = true },
            shape=RecipeUiDefaults.ButtonShape,
            modifier = Modifier.heightIn(min=48.dp).testTag("recipe-sort-trigger")
        ) {
            Text("정렬: ${selected.label} ⌄", style=MaterialTheme.typography.labelMedium)
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DishSort.entries.forEach { type ->
                DropdownMenuItem(
                    text = { Text(type.label) },
                    onClick = {
                        onSelected(type)
                        expanded = false
                    },
                    modifier = Modifier.heightIn(min=48.dp).testTag("recipe-sort-${type.name}")
                )
            }
        }
    }
}
