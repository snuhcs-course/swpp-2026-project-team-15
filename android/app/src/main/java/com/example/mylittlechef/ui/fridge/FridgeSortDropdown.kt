// AI-assisted with Codex, 2026-11-02; human review pending.
package com.example.mylittlechef.ui.fridge

import androidx.compose.foundation.layout.Box
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import com.example.mylittlechef.domain.FridgeSortType

@Composable
fun FridgeSortDropdown(
    selected: FridgeSortType,
    onSelected: (FridgeSortType) -> Unit,
    modifier: Modifier = Modifier
) {
    var expanded by remember { mutableStateOf(false) }
    Box(modifier) {
        OutlinedButton(
            onClick = { expanded = true },
            modifier = Modifier.testTag("fridge-sort-trigger")
        ) { Text("정렬: ${selected.label} ⌄") }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            FridgeSortType.entries.forEach { type ->
                DropdownMenuItem(
                    text = { Text(type.label) },
                    onClick = { onSelected(type); expanded = false },
                    modifier = Modifier.testTag("fridge-sort-${type.name}")
                )
            }
        }
    }
}
