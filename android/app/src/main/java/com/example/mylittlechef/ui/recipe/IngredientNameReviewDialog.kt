// AI-assisted explicit ingredient correction, 2026-11-10; human review pending.
package com.example.mylittlechef.ui.recipe

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.domain.IngredientNames
import com.example.mylittlechef.viewmodel.FridgeViewModel

@Composable
fun IngredientNameReviewDialog(name: String, candidates: List<String>, catalog: List<String>,
    fridge: FridgeViewModel, onClose: () -> Unit) {
    var value by rememberSaveable(name) { mutableStateOf("") }
    LaunchedEffect(fridge.ingredients) { if(fridge.ingredients.none { it.name == name }) onClose() }
    val options = (candidates + catalog.filter {
        value.isNotBlank() && IngredientNames.normalize(it).contains(IngredientNames.normalize(value))
    }).distinct().take(8)
    AlertDialog(onDismissRequest = { if(!fridge.isSavingIngredients) onClose() }, title = { Text("재료 이름 확인") },
        text = { Column(Modifier.verticalScroll(rememberScrollState()),verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text("‘$name’은 등록된 재료와 연결되지 않았어요. 같은 재료인지 확인하고 이름을 선택해 주세요.")
            OutlinedTextField(value,onValueChange = { value = it },label = { Text("등록된 재료 찾기") },singleLine = true)
            options.forEach { option -> TextButton(onClick = { value = option }) { Text(option) } }
            Text("변경 전에는 현재 냉장고 이름을 그대로 유지해요.",style = MaterialTheme.typography.bodySmall)
            fridge.ingredientSaveError?.let { Text(it,color = MaterialTheme.colorScheme.error) }
        } },
        confirmButton = { TextButton(enabled = value in (catalog + candidates) && !fridge.isSavingIngredients,
            onClick = { fridge.renameIngredient(name,value) }) { Text("이 이름으로 변경") } },
        dismissButton = { TextButton(enabled = !fridge.isSavingIngredients,onClick = onClose) { Text("그대로 두기") } })
}
