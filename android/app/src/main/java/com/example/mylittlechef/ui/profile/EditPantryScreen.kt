// Restored and integrated with Codex, 2026-10-29; human review pending.
// AI-assisted with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
package com.example.mylittlechef.ui.profile

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import com.example.mylittlechef.model.Preset
import com.example.mylittlechef.ui.onboarding.PantrySelectionContent
import com.example.mylittlechef.viewmodel.FridgeViewModel

@Composable
fun EditPantryScreen(
    fridge: FridgeViewModel,
    onBackClick: () -> Unit,
    onSaveClick: () -> Unit
) {
    val options = Preset.pantrySeasonings + Preset.pantryBasics
    var selected by rememberSaveable {
        mutableStateOf(options.filter { option ->
            fridge.ingredients.any { it.name == option }
        })
    }

    BackHandler(enabled = fridge.isSavingPantry) { /* Wait for the atomic write. */ }

    EditProfileScaffold(
        onBackClick = { if (!fridge.isSavingPantry) onBackClick() },
        onSaveClick = {
            fridge.updatePantryItems(selected, onSaved = onSaveClick)
        },
        title = "기본 재료·조미료 설정"
    ) {
        Column {
            fridge.pantryError?.let { Text(it) }
            if (fridge.isSavingPantry) Text("저장하고 있어요…")
            PantrySelectionContent(
                selected = selected,
                onSelectedChange = { if (!fridge.isSavingPantry) selected = it }
            )
        }
    }
}
