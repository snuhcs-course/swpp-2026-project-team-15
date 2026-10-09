// AI-generated initial IngredientItem, EditableIngredientList, IngredientRow, and IngredientEditorState drafts with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
package com.example.mylittlechef.ui.fridge.components

import androidx.annotation.DrawableRes
import androidx.compose.runtime.Composable
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.R

import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.ui.components.DashedButton
import com.example.mylittlechef.ui.components.TextOnlyButton

import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.ui.theme.Gray

@Composable
fun IngredientItem(
    ingredient: Ingredient,
    modifier: Modifier = Modifier,
    imageSize: Dp = 45.dp
)
{
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally
    )
    {
        val imageRes = ingredient.imageRes
        if (imageRes != null) {
            Image(
                painter = painterResource(imageRes),
                contentDescription = ingredient.name,
                modifier = Modifier
                    .size(imageSize)
                    .clip(CircleShape),
                contentScale = ContentScale.Crop
            )
        }
        else {
            Box(
                modifier = Modifier
                    .size(imageSize)
                    .clip(CircleShape)
                    .background(DeepGreen)
            )
        }

        Spacer(Modifier.height(7.dp))

        Text(
            text = ingredient.name,
            style = MaterialTheme.typography.labelSmall,
            color = Color.Black,
            textAlign = TextAlign.Center,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )

    }
}

@Composable
fun EditableIngredientList(
    editor: IngredientEditorState,
    modifier: Modifier = Modifier
)
{
    Column(
        modifier = modifier
            .verticalScroll(rememberScrollState())
            .padding(
                top = 8.dp,
                start = 24.dp,
                end = 24.dp,
                bottom = 16.dp
            ),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    )
    {
        editor.ingredients.forEachIndexed { i, ingredient ->
            IngredientRow(
                name = ingredient.name,
                isEditing = editor.editingIndex == i,
                onNameChange = { editor.rename(i, it) },
                onEditClick = { editor.toggleEdit(i) },
                onRemoveClick = { editor.remove(i) },
                imageRes = ingredient.imageRes
            )
        }

        DashedButton(
            text = "+ 식재료 추가",
            onClick = editor::startAdd,
            modifier = Modifier
                .fillMaxWidth()
        )
    }
}

@Composable
fun IngredientRow(
    name: String, // name of ingredient
    isEditing: Boolean,
    onNameChange: (String) -> Unit,
    onEditClick: () -> Unit, // when the edit icon is clicked
    onRemoveClick: () -> Unit, // when the remove icon is clicked
    modifier: Modifier = Modifier,
    @DrawableRes imageRes: Int? = null
)
{
    Box(
        modifier = modifier.fillMaxWidth()
    )
    {
        // Row for ingredient content
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 56.dp)
                .clip(RoundedCornerShape(15.dp))
                .background(Gray)
                .padding(
                    start = 24.dp,
                    end = 12.dp,
                    top = 4.dp,
                    bottom = 4.dp
                ),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        )
        {
            if (isEditing) {
                OutlinedTextField(
                    value = name,
                    onValueChange = onNameChange,
                    modifier = Modifier.weight(1f),
                    keyboardOptions = KeyboardOptions(
                        imeAction = ImeAction.Done
                    ),
                    keyboardActions = KeyboardActions(
                        onDone = {
                            onEditClick()
                        }
                    )
                )
            }
            else {
                // Text for ingredient name
                Text(
                    text = name,
                    style = MaterialTheme.typography.bodyLarge,
                    color = Color.Black,
                    overflow = TextOverflow.Ellipsis
                )

                // IconButton for edit click
                IconButton(
                    onClick = onEditClick,
                    modifier = Modifier
                        .size(15.dp)
                )
                {
                    Icon(
                        painter = painterResource(R.drawable.ic_edit),
                        contentDescription = "edit",
                        tint = Color.Black
                    )
                }

                //Spacer(Modifier.weight(1f))

            }

            // ingredient image
            if (imageRes != null) {
                Image(
                    painter = painterResource(imageRes),
                    contentDescription = name,
                    modifier = Modifier
                        .size(40.dp)
                        .clip(CircleShape),
                    contentScale = ContentScale.Crop
                )
            }
        }

        if (!isEditing) {
            // IconButton for remove click
            IconButton(
                onClick = onRemoveClick,
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .size(24.dp)
                    .offset(x = 6.dp, y = (-6).dp)
            )
            {
                Icon(
                    painter = painterResource(R.drawable.ic_remove),
                    contentDescription = "remove",
                    tint = Color.Unspecified
                )
            }
        }
    }
}

@Stable
class IngredientEditorState(
    initial: List<Ingredient> = emptyList()
)
{
    val ingredients = mutableStateListOf<Ingredient>()

    var editingIndex by mutableStateOf<Int?>(null)
        private set

    // TODO: implement

    fun replaceAll(list: List<Ingredient>) {
        ingredients.clear()
        ingredients.addAll(list)
        editingIndex = null
    }

    fun startAdd() {
        finishEdit()
        val ingredient = Ingredient(name = "")
        ingredients.add(ingredient)
        editingIndex = ingredients.indexOf(ingredient)
    }

    fun toggleEdit(index: Int) {
        if (editingIndex == index) {
            finishEdit()
        }
        else {
            finishEdit()
            editingIndex = index
        }
    }

    fun rename(index: Int, name: String) {
        ingredients[index] = ingredients[index].copy(name = name)
    }

    fun remove(index: Int) {
        ingredients.removeAt(index)
        if (editingIndex == index) editingIndex = null
    }

    fun finishEdit() {
        val index = editingIndex ?: return

        if (ingredients[index].name.isBlank()) {
            ingredients.removeAt(index)
        }

        editingIndex = null
    }
}

@Composable
fun rememberIngredientEditorState(
    initial: List<Ingredient> = emptyList()
): IngredientEditorState = remember { IngredientEditorState(initial)  }
