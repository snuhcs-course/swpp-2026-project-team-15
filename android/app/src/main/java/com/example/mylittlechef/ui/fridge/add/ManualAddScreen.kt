// AI-generated initial manual-entry scaffold with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
// Ingredient name completion added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
package com.example.mylittlechef.ui.fridge.add

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxSize
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
    val editor = rememberIngredientEditorState()
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
    AddFlowScaffold(
        onBackClick = onBackClick,
        title = "추가할 재료들을 입력해 주세요",
        bottomContent = {
            NormalButton(
                text = "냉장고에 반영",
                buttonColor = DeepGreen,
                textColor = Color.White,
                onClick = {
                    editor.finishEdit()
                    if (editor.ingredients.isNotEmpty()) {
                        fridge.addIngredients(editor.ingredients)
                    }
                    onSaveClick()
                }
            )
        }
    )
    {
        EditableIngredientList(
            editor = editor,
            ingredientNames = ingredientNames,
            modifier = Modifier.fillMaxSize()
        )
    }
}
