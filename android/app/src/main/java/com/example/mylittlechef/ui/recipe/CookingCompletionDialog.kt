// UAT stage 4 assisted by Codex, 2026-11-24; human review pending.
// AI-assisted HE cooking completion, 2026-11-10; human review pending.
// Restored on the YouTube-based recipes with Claude Code (Opus 5.5), 2026-11-20: the choices come from the
// stored recipe's rows the fridge holds; only what the user ticks is removed.
package com.example.mylittlechef.ui.recipe

import androidx.compose.foundation.BorderStroke
import com.example.mylittlechef.ui.components.DragSelectionGroup
import com.example.mylittlechef.ui.components.IngredientBadge
import com.example.mylittlechef.ui.components.LocalSelectionTargets
import com.example.mylittlechef.ui.components.selectionTarget
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.selected
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
import com.example.mylittlechef.model.Preset
import com.example.mylittlechef.viewmodel.FridgeViewModel

/**
 * Fridge items the recipe used: an owned row with the same name is ticked to start with, except pantry seasonings; a fridge name that only
 * contains a row name, or the other way round (청양고추 for 고추), is offered unticked, since it may be another item.
 */
internal fun usedFridgeItems(recipe: DishRecipe, fridgeNames: List<String>): Pair<List<String>, Set<String>> {
    val owned = recipe.ingredients.filter { it.availability == Availability.OWNED }.map { it.name.replace(" ", "") }
    val exact = fridgeNames.filter { name -> owned.any { it == name.replace(" ", "") } }
    val related = fridgeNames.filter { name ->
        val key = name.replace(" ", "")
        name !in exact && key.length >= 2 && owned.any { row -> row.length >= 2 && (row.contains(key) || key.contains(row)) }
    }
    // Pantry seasonings are used a little at a time, so they are offered but never ticked to start with.
    val seasonings = Preset.pantrySeasonings.map { it.replace(" ", "") }.toSet()
    return (exact + related) to exact.filterNot { it.replace(" ", "") in seasonings }.toSet()
}

@Composable
fun CookingCompletionDialog(dishId: String, recipe: DishRecipe, fridge: FridgeViewModel, onClose: () -> Unit) {
    // Offer only currently held recipe-related items. Availability may have changed during cooking.
    val choices = remember(recipe,fridge.ingredients) {
        usedFridgeItems(recipe.copy(ingredients=recipe.ingredients.map {it.copy(availability=Availability.OWNED)}),
            fridge.ingredients.map {it.name}).first
    }
    var selected by rememberSaveable(dishId) { mutableStateOf(emptyList<String>()) }
    LaunchedEffect(choices) { selected=selected.filter {it in choices} }
    val before = rememberSaveable { fridge.pendingRemoval?.id ?: -1L }
    var requested by rememberSaveable { mutableStateOf(false) }
    var completed by rememberSaveable { mutableStateOf<Long?>(null) }
    val receipt = fridge.pendingRemoval
    LaunchedEffect(receipt?.id) {
        if(requested && receipt != null && receipt.id != before) completed = receipt.id
    }
    val busy = fridge.isRemovingIngredients || fridge.isRestoringIngredients || fridge.isSavingIngredients || fridge.isSavingPantry || fridge.isSavingSuggestion
    AlertDialog(onDismissRequest = { if(!busy) onClose() },shape=RecipeUiDefaults.DialogShape,
        title = { Text(if(completed == null) "소진한 재료가 있나요?" else "재료를 정리했어요") },
        text = {
            Column(Modifier.heightIn(max=360.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                if(completed == null) {
                    Text("다 쓴 재료만 골라 주세요. 남아 있는 재료는 유지해요.")
                    if(choices.isEmpty()) Text("이 요리에 연결되는 보유 재료가 없어요.")
                    DragSelectionGroup(selected.toSet(),{selected=it.filter {name->name in choices}},modifier=Modifier.testTag("consumed-choices"),enabled=!busy) {
                        Column(verticalArrangement=Arrangement.spacedBy(8.dp)) {
                            choices.forEach { name ->
                                ConsumedIngredientRow(name,name in selected,!busy) { checked ->
                                    selected=if(checked) (selected+name).distinct() else selected-name
                                }
                            }
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
            if(completed == null) TextButton(colors=ButtonDefaults.textButtonColors(contentColor=MaterialTheme.colorScheme.error),
                enabled = !busy && selected.any { it in choices }, onClick = {
                requested = true
                fridge.removeIngredients(selected.filter { it in choices }.toSet())
            }, modifier = Modifier.testTag("consumed-confirm")) { Text(if(busy) "저장 중" else "선택한 재료 삭제") }
            else if(receipt?.id == completed) TextButton(enabled = !busy, onClick = { receipt?.let { fridge.undoRemoval(it.id) } }) { Text("실행 취소") }
        },
        dismissButton = { TextButton(enabled = !busy, onClick = onClose) { Text(if(completed == null) "그대로 두기" else "닫기") } })
}

/** Same catalog disc/check as fridge management; selection remains a draft until confirmation. */
@Composable
private fun ConsumedIngredientRow(name:String,checked:Boolean,enabled:Boolean,onCheckedChange:(Boolean)->Unit) {
    val gestures=LocalSelectionTargets.current
    Surface(Modifier.fillMaxWidth().heightIn(min=64.dp).selectionTarget(name)
        .testTag("consumed-$name").semantics {selected=checked}
        .toggleable(checked,enabled=enabled,role=Role.Checkbox,onValueChange={
            if(gestures?.suppressClick!=true) onCheckedChange(it)
        }),shape=RecipeUiDefaults.CardShape,color=MaterialTheme.colorScheme.surface,
        border=BorderStroke(1.dp,if(checked) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant)) {
        Row(Modifier.padding(12.dp),verticalAlignment=Alignment.CenterVertically,
            horizontalArrangement=Arrangement.spacedBy(12.dp)) {
            IngredientBadge(name,size=40.dp,selected=checked)
            Text(name,style=MaterialTheme.typography.bodyMedium,modifier=Modifier.weight(1f))
        }
    }
}
