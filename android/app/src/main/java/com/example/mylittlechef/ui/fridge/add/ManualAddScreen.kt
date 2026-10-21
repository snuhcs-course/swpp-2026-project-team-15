// AI-generated initial manual-entry scaffold with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
package com.example.mylittlechef.ui.fridge.add

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import com.example.mylittlechef.ui.components.NormalButton
import com.example.mylittlechef.ui.fridge.components.AddFlowScaffold
import com.example.mylittlechef.ui.fridge.components.EditableIngredientList
import com.example.mylittlechef.ui.fridge.components.IngredientEditorState
import com.example.mylittlechef.ui.fridge.components.rememberIngredientEditorState
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.viewmodel.FridgeViewModel

@Composable
fun ManualAddScreen(
    fridge: FridgeViewModel,
    onBackClick: () -> Unit,
    onSaveClick: () -> Unit,
    modifier: Modifier = Modifier
)
{
    val editor = rememberIngredientEditorState()
    ManualAddContent(
        fridge = fridge,
        editor = editor,
        onBackClick = onBackClick,
        onSaveClick = onSaveClick,
        modifier = modifier
    )
}

@Composable
private fun ManualAddContent(
    fridge: FridgeViewModel,
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
            modifier = Modifier.fillMaxSize()
        )
    }
}
