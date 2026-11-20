// AI-assisted with Codex, 2026-11-02; human review pending.
package com.example.mylittlechef.ui.fridge

import androidx.compose.foundation.layout.Box
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.layout.heightIn
import androidx.compose.ui.unit.dp
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
            shape=RoundedCornerShape(10.dp),
            modifier = Modifier.heightIn(min=48.dp).testTag("fridge-sort-trigger")
        ) { Text("정렬: ${selected.label} ⌄", style=MaterialTheme.typography.labelMedium) }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            FridgeSortType.entries.forEach { type ->
                DropdownMenuItem(
                    text = { Text(type.label) },
                    onClick = { onSelected(type); expanded = false },
                    modifier = Modifier.heightIn(min=48.dp).testTag("fridge-sort-${type.name}")
                )
            }
        }
    }
}
