// AI-assisted with Codex (GPT-6.1 Sol), 2026-10-14; human review pending.
package com.example.mylittlechef.ui.recipe

import androidx.compose.foundation.layout.Box
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import com.example.mylittlechef.domain.RecipeSortType

@Composable
fun RecipeSortDropdown(
    selected: RecipeSortType,
    onSelected: (RecipeSortType) -> Unit,
    modifier: Modifier = Modifier
) {
    var expanded by remember { mutableStateOf(false) }
    Box(modifier) {
        OutlinedButton(
            onClick = { expanded = true },
            modifier = Modifier.testTag("recipe-sort-trigger")
        ) {
            Text("정렬: ${selected.label} ⌄")
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            RecipeSortType.entries.forEach { type ->
                DropdownMenuItem(
                    text = { Text(type.label) },
                    onClick = {
                        onSelected(type)
                        expanded = false
                    },
                    modifier = Modifier.testTag("recipe-sort-${type.name}")
                )
            }
        }
    }
}
