// UX2 layout/lifecycle changes assisted by Codex, 2026-11-19; human review pending.
// UI ergonomics and theme changes assisted by Codex, 2026-11-03; human review pending.
// Fridge presentation/sorting and arrival-order updates assisted by Codex, 2026-11-02; human review pending.
// AI-generated initial IngredientItem, EditableIngredientList, IngredientRow, and IngredientEditorState drafts with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
// Ingredient name completion added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
package com.example.mylittlechef.ui.fridge.components

import androidx.annotation.DrawableRes
import androidx.compose.runtime.Composable
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.material3.TextButton
import androidx.compose.material3.Surface
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.saveable.Saver
import androidx.compose.runtime.saveable.rememberSaveable
import com.google.gson.Gson
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.testTag
import com.example.mylittlechef.domain.IngredientAppearance
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
    imageSize: Dp = 45.dp,
    appearance: IngredientAppearance? = null
)
{
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally
    )
    {
        val imageRes = ingredient.imageRes
        if (appearance != null) {
            Box(
                modifier = Modifier.size(imageSize).clip(RoundedCornerShape(imageSize * 0.36f))
                    .background(Color(appearance.backgroundArgb)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    painter = painterResource(ingredientIconResource(if(ingredient.name=="감자") "potato" else if(ingredient.name in listOf("고추","청고추","홍고추","청양고추")) "chili" else appearance.iconKey)),
                    contentDescription = ingredient.name,
                    tint = Color(0xFF172C25),
                    modifier = Modifier.size(imageSize * 0.82f).testTag("ingredient-icon-" + ingredient.name)
                )
            }
        }
        else if (imageRes != null) {
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
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurface,
            textAlign = TextAlign.Center,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis
        )

    }
}

@Composable
fun EditableIngredientList(
    editor: IngredientEditorState,
    ingredientNames: List<String> = emptyList(),
    modifier: Modifier = Modifier,
    enabled: Boolean = true
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
        Text("한 번에 여러 재료를 추가할 수 있어요. 이름을 누르면 수정할 수 있어요.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        editor.removedName?.let { name ->
            Surface(color = MaterialTheme.colorScheme.secondaryContainer, shape = RoundedCornerShape(12.dp)) {
                Row(Modifier.fillMaxWidth().padding(start = 12.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("${name.ifBlank { "빈 항목" }} 삭제됨", Modifier.weight(1f),
                        color = MaterialTheme.colorScheme.onSecondaryContainer)
                    TextButton(onClick = editor::undoRemove, enabled = enabled, modifier = Modifier.testTag("undo-candidate-removal")) {
                        Text("실행 취소")
                    }
                    TextButton(onClick = editor::dismissUndo, enabled = enabled) { Text("닫기") }
                }
            }
        }
        editor.ingredients.forEachIndexed { i, ingredient ->
            IngredientRow(
                name = ingredient.name,
                isEditing = editor.editingIndex == i,
                onNameChange = { editor.rename(i, it) },
                onEditClick = { editor.toggleEdit(i) },
                onRemoveClick = { editor.remove(i) },
                suggestions = if (editor.editingIndex == i) {
                    ingredientNames
                        .asSequence()
                        .filter { name ->
                            ingredient.name.trim().isNotEmpty() &&
                                name.contains(ingredient.name.trim(), ignoreCase = true) &&
                                editor.ingredients.withIndex().none { (index, row) ->
                                    index != i && row.name.equals(name, ignoreCase = true)
                                }
                        }
                        .sortedWith(
                            compareBy<String> {
                                !it.equals(ingredient.name.trim(), ignoreCase = true)
                            }.thenBy {
                                !it.startsWith(ingredient.name.trim(), ignoreCase = true)
                            }.thenBy { it.length }.thenBy { it }
                        )
                        .take(5)
                        .toList()
                } else {
                    emptyList()
                },
                onSuggestionSelected = { selected ->
                    editor.rename(i, selected)
                    editor.finishEdit()
                },
                imageRes = ingredient.imageRes,
                enabled = enabled
            )
            ingredient.recognition?.let { evidence ->
                Text(if (evidence.needsReview) "확인 필요 · 사진과 비교해 주세요" else "사진과 비교해 확인해 주세요",
                    style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (evidence.rawTexts.isNotEmpty()) {
                    Text("인식한 내용: ${evidence.rawTexts.joinToString(", ")}",
                        style = MaterialTheme.typography.bodySmall, maxLines = 2, overflow = TextOverflow.Ellipsis)
                }
                if (ingredient.name != evidence.suggestedName) {
                    Text("처음 제안한 이름: ${evidence.suggestedName}", style = MaterialTheme.typography.bodySmall)
                }
            }
        }

        DashedButton(
            text = "+ 식재료 추가",
            onClick = editor::startAdd,
            enabled = enabled,
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
    suggestions: List<String> = emptyList(),
    onSuggestionSelected: (String) -> Unit = {},
    modifier: Modifier = Modifier,
    @DrawableRes imageRes: Int? = null,
    enabled: Boolean = true
)
{
    Column(
        modifier = modifier.fillMaxWidth()
    )
    {
        Box {
        // Row for ingredient content
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .heightIn(min = 56.dp)
                .clip(RoundedCornerShape(15.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant)
                .padding(
                    start = 12.dp,
                    end = 48.dp,
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
                    enabled = enabled,
                    placeholder = { Text("재료 이름") },
                    singleLine = true,
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
                    modifier = Modifier.weight(1f).clickable(enabled = enabled, onClick = onEditClick),
                    style = MaterialTheme.typography.bodyLarge,
                    color = MaterialTheme.colorScheme.onSurface,
                    overflow = TextOverflow.Ellipsis
                )

                // IconButton for edit click
                IconButton(
                    onClick = onEditClick,
                    enabled = enabled,
                    modifier = Modifier
                        .size(48.dp)
                )
                {
                    Icon(
                        painter = painterResource(R.drawable.ic_edit),
                        contentDescription = "$name 수정",
                        tint = MaterialTheme.colorScheme.onSurface
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
                enabled = enabled,
                modifier = Modifier
                    .align(Alignment.TopEnd)
                    .size(48.dp)
                    .offset(x = 6.dp, y = (-6).dp)
            )
            {
                Icon(
                    painter = painterResource(R.drawable.ic_remove),
                    contentDescription = "$name 삭제",
                    tint = Color.Unspecified
                )
            }
        }
        }

        if (isEditing && suggestions.isNotEmpty()) {
            // Scroll the whole list into view: the phone test (2026-11-19) found the third
            // suggestion hidden behind the bottom button while the keyboard was open.
            val shown = remember { BringIntoViewRequester() }
            LaunchedEffect(suggestions) { shown.bringIntoView() }
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .bringIntoViewRequester(shown)
                    .padding(top = 4.dp)
                    .clip(RoundedCornerShape(12.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant)
            ) {
                suggestions.forEach { suggestion ->
                    Text(
                        text = suggestion,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { onSuggestionSelected(suggestion) }
                            .padding(horizontal = 20.dp, vertical = 12.dp)
                    )
                }
            }
        }
    }
}

@Stable
class IngredientEditorState(
    initial: List<Ingredient> = emptyList()
)
{
    val ingredients = mutableStateListOf<Ingredient>().apply { addAll(initial) }
    private data class RemovedRow(val item: Ingredient, val index: Int)
    private data class SavedEditor(val rows: List<Ingredient>, val editing: Int?, val removed: RemovedRow?)
    companion object {
        val StateSaver = Saver<IngredientEditorState, String>(
            save = { Gson().toJson(SavedEditor(it.ingredients.toList(), it.editingIndex, it.removedRow)) },
            restore = { encoded -> runCatching {
                val saved = Gson().fromJson(encoded, SavedEditor::class.java)
                IngredientEditorState(checkNotNull(saved.rows)).apply {
                    editingIndex = saved.editing?.takeIf { it in ingredients.indices }
                    removedRow = saved.removed
                }
            }.getOrNull() }
        )
    }
    private var removedRow by mutableStateOf<RemovedRow?>(null)
    val removedName: String? get() = removedRow?.item?.name

    fun dismissUndo() { removedRow = null }

    fun undoRemove() {
        val row = removedRow ?: return
        val index = row.index.coerceIn(0, ingredients.size)
        ingredients.add(index, row.item)
        editingIndex = editingIndex?.let { if (it >= index) it + 1 else it }
        removedRow = null
    }

    var editingIndex by mutableStateOf<Int?>(null)
        private set

    fun replaceAll(list: List<Ingredient>) {
        ingredients.clear()
        ingredients.addAll(list)
        editingIndex = null
        removedRow = null
    }

    fun startAdd() {
        finishEdit()
        val ingredient = Ingredient(name = "")
        ingredients.add(ingredient)
        editingIndex = ingredients.lastIndex
    }

    fun toggleEdit(index: Int) {
        if (index !in ingredients.indices) return
        if (editingIndex == index) {
            finishEdit()
        }
        else {
            val previous = editingIndex
            val shifts = previous != null && previous < index && ingredients[previous].name.isBlank()
            finishEdit()
            editingIndex = if (shifts) index - 1 else index
        }
    }

    fun rename(index: Int, name: String) {
        if (index !in ingredients.indices) return
        ingredients[index] = ingredients[index].copy(name = name)
    }

    fun remove(index: Int) {
        if (index !in ingredients.indices) return
        removedRow = RemovedRow(ingredients.removeAt(index), index)
        editingIndex = editingIndex?.let { when {
            it == index -> null
            it > index -> it - 1
            else -> it
        } }
    }

    fun finishEdit() {
        val index = editingIndex ?: return

        if (index in ingredients.indices && ingredients[index].name.isBlank()) {
            ingredients.removeAt(index)
        }

        editingIndex = null
    }
}

@Composable
fun rememberIngredientEditorState(
    initial: List<Ingredient> = emptyList(),
    startWithInput: Boolean = false
): IngredientEditorState = rememberSaveable(saver = IngredientEditorState.StateSaver) {
    IngredientEditorState(initial).apply { if (startWithInput && initial.isEmpty()) startAdd() }
}
