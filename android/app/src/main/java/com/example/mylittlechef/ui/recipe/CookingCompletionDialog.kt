// AI-assisted HE cooking completion, 2026-11-10; human review pending.
// Restored on the YouTube-based recipes with Claude Code (Opus 5.5), 2026-11-20: the choices come from the
// stored recipe's rows the fridge holds; only what the user ticks is removed.
package com.example.mylittlechef.ui.recipe

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.domain.Availability
import com.example.mylittlechef.domain.DishRecipe
import com.example.mylittlechef.viewmodel.FridgeViewModel

/**
 * Fridge items the recipe used: an owned row with the same name is ticked to start with; a fridge name that only
 * contains a row name, or the other way round (청양고추 for 고추), is offered unticked, since it may be another item.
 */
internal fun usedFridgeItems(recipe: DishRecipe, fridgeNames: List<String>): Pair<List<String>, Set<String>> {
    val owned = recipe.ingredients.filter { it.availability == Availability.OWNED }.map { it.name.replace(" ", "") }
    val exact = fridgeNames.filter { name -> owned.any { it == name.replace(" ", "") } }
    val related = fridgeNames.filter { name ->
        val key = name.replace(" ", "")
        name !in exact && key.length >= 2 && owned.any { row -> row.length >= 2 && (row.contains(key) || key.contains(row)) }
    }
    return (exact + related) to exact.toSet()
}

@Composable
fun CookingCompletionDialog(dishId: String, recipe: DishRecipe, fridge: FridgeViewModel, onClose: () -> Unit) {
    val (choices, ticked) = remember(recipe, fridge.ingredients) { usedFridgeItems(recipe, fridge.ingredients.map { it.name }) }
    var selected by rememberSaveable(dishId) { mutableStateOf(ticked.toList()) }
    val before = rememberSaveable { fridge.pendingRemoval?.id ?: -1L }
    var requested by rememberSaveable { mutableStateOf(false) }
    var completed by rememberSaveable { mutableStateOf<Long?>(null) }
    val receipt = fridge.pendingRemoval
    LaunchedEffect(receipt?.id) {
        if(requested && receipt != null && receipt.id != before) completed = receipt.id
    }
    val busy = fridge.isRemovingIngredients || fridge.isRestoringIngredients || fridge.isSavingIngredients
    AlertDialog(onDismissRequest = { if(!busy) onClose() },
        title = { Text(if(completed == null) "소진한 재료가 있나요?" else "재료를 정리했어요") },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if(completed == null) {
                    Text("다 쓴 재료만 골라 주세요. 남아 있는 재료는 유지해요.")
                    if(choices.isEmpty()) Text("이 요리에 연결되는 보유 재료가 없어요.")
                    choices.forEach { name ->
                        Row(Modifier.fillMaxWidth().toggleable(name in selected, enabled = !busy, role = Role.Checkbox,
                            onValueChange = { value -> selected = if(value) selected + name else selected - name })
                            .padding(vertical = 6.dp).testTag("consumed-$name"), verticalAlignment = Alignment.CenterVertically) {
                            Checkbox(name in selected, onCheckedChange = null)
                            Text(name)
                        }
                    }
                    fridge.removalError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                } else {
                    Text(if(receipt?.id == completed) "선택한 재료만 냉장고에서 삭제했어요." else "삭제를 취소했어요.")
                    fridge.undoError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                }
            }
        },
        confirmButton = {
            if(completed == null) TextButton(enabled = !busy && selected.any { it in choices }, onClick = {
                requested = true
                fridge.removeIngredients(selected.filter { it in choices }.toSet())
            }, modifier = Modifier.testTag("consumed-confirm")) { Text(if(busy) "저장 중" else "선택한 재료 삭제") }
            else if(receipt?.id == completed) TextButton(enabled = !busy, onClick = { receipt?.let { fridge.undoRemoval(it.id) } }) { Text("실행 취소") }
        },
        dismissButton = { TextButton(enabled = !busy, onClick = onClose) { Text(if(completed == null) "그대로 두기" else "닫기") } })
}
