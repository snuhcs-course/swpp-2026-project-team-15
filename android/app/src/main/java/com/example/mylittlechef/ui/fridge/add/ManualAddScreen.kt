// UX2 layout/lifecycle changes assisted by Codex, 2026-11-19; human review pending.
// UI ergonomics and theme changes assisted by Codex, 2026-11-03; human review pending.
// AI-generated initial manual-entry scaffold with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
// Ingredient name completion added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
package com.example.mylittlechef.ui.fridge.add

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Button
import androidx.compose.material3.Text
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.ui.unit.dp
import androidx.activity.compose.BackHandler

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import com.example.mylittlechef.ui.components.NormalButton
import com.example.mylittlechef.ui.fridge.components.AddFlowScaffold
import com.example.mylittlechef.ui.fridge.components.EditableIngredientList
import com.example.mylittlechef.ui.fridge.components.IngredientEditorState
import com.example.mylittlechef.ui.fridge.components.rememberIngredientEditorState
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.IngredientCatalogViewModel

@Composable
fun ManualAddScreen(
    fridge: FridgeViewModel,
    ingredientCatalog: IngredientCatalogViewModel,
    onBackClick: () -> Unit,
    onSaveClick: () -> Unit,
    modifier: Modifier = Modifier
)
{
    val editor = rememberIngredientEditorState(startWithInput = true)
    LaunchedEffect(ingredientCatalog) { ingredientCatalog.load() }
    ManualAddContent(
        fridge = fridge,
        ingredientNames = ingredientCatalog.names,
        editor = editor,
        onBackClick = onBackClick,
        onSaveClick = onSaveClick,
        modifier = modifier
    )
}

@Composable
private fun ManualAddContent(
    fridge: FridgeViewModel,
    ingredientNames: List<String>,
    editor: IngredientEditorState,
    onBackClick: () -> Unit,
    onSaveClick: () -> Unit,
    modifier: Modifier = Modifier
)
{
    val save = rememberIngredientSave(fridge, onSaveClick)
    val sheet = LocalEntrySheet.current
    // Read snapshots in this composition, not inside SideEffect, so typing updates the guard.
    val hasDraft = editor.ingredients.any { it.name.isNotBlank() }
    val saveBusy = save.busy
    SideEffect { sheet?.busy = saveBusy; sheet?.draft = hasDraft }
    BackHandler(enabled = save.busy) { }
    AddFlowScaffold(
        onBackClick = { if (!save.busy) onBackClick() },
        modifier = modifier,
        title = "재료 직접 입력",
        bottomContent = {
            fridge.ingredientSaveError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            Button(
                modifier = Modifier.fillMaxWidth(0.8f).heightIn(min = 52.dp),
                enabled = !save.busy && editor.ingredients.any { it.name.isNotBlank() },
                onClick = {
                    editor.finishEdit()
                    save.submit(editor.ingredients.toList())
                }
            ) { Text(if (fridge.isSavingIngredients) "저장 중" else "저장") }
        }
    )
    {
        EditableIngredientList(
            editor = editor,
            ingredientNames = ingredientNames,
            modifier = Modifier.fillMaxSize(),
            enabled = !save.busy
        )
    }
}
