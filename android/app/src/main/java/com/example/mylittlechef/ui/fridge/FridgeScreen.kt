// Multi-selection fridge actions assisted by Codex, 2026-11-03; human review pending.
// AI-generated initial fridge-screen scaffold with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
package com.example.mylittlechef.ui.fridge

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.R
import com.example.mylittlechef.data.local.IngredientPresentationProvider
import com.example.mylittlechef.domain.FridgeSortType
import com.example.mylittlechef.domain.IngredientPresentationCatalog
import com.example.mylittlechef.domain.sortFridgeIngredients
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.ui.components.TitleText
import com.example.mylittlechef.ui.fridge.components.FridgeShelves
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.IngredientSuggestionViewModel
import com.example.mylittlechef.viewmodel.UserViewModel

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun FridgeScreen(
    user: UserViewModel,
    fridge: FridgeViewModel,
    onAddIngredientClick: () -> Unit,
    modifier: Modifier = Modifier,
    ingredientSuggestions: IngredientSuggestionViewModel? = null
) {
    val context = LocalContext.current.applicationContext
    val appearanceCatalog = remember(context) { IngredientPresentationProvider.get(context) }
    var showSuggestions by rememberSaveable { mutableStateOf(false) }
    LaunchedEffect(showSuggestions, fridge.ingredients) {
        if (showSuggestions) ingredientSuggestions?.refresh(fridge.ingredients)
    }
    val snackbar = remember { SnackbarHostState() }
    LaunchedEffect(fridge.removalError) {
        fridge.removalError?.let { message ->
            snackbar.showSnackbar(message, actionLabel = "확인", duration = SnackbarDuration.Long)
            fridge.dismissRemovalError()
        }
    }
    Box(modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        FridgeContent(
            nickname = user.nickname,
            ingredients = fridge.ingredients,
            controlsEnabled = fridge.removingIngredient == null && !fridge.isRemovingIngredients && !fridge.isSavingPantry,
            onRemoveIngredients = fridge::removeIngredients,
            onAddIngredientClick = onAddIngredientClick,
            onSuggestionsClick = { showSuggestions = true },
            appearanceCatalog = appearanceCatalog
        )
        SnackbarHost(snackbar, Modifier.align(Alignment.BottomCenter))
    }
    if (showSuggestions && ingredientSuggestions != null) {
        ModalBottomSheet(onDismissRequest = { showSuggestions = false }) {
            IngredientSuggestionSheet(ingredientSuggestions, onRetry = { ingredientSuggestions.refresh(fridge.ingredients) })
        }
    }
}

@Composable
private fun FridgeContent(
    nickname: String,
    ingredients: List<Ingredient>,
    controlsEnabled: Boolean,
    onRemoveIngredients: (Set<String>, () -> Unit) -> Unit,
    onAddIngredientClick: () -> Unit,
    onSuggestionsClick: () -> Unit,
    appearanceCatalog: IngredientPresentationCatalog,
    modifier: Modifier = Modifier
) {
    var selecting by rememberSaveable { mutableStateOf(false) }
    var selectedNames by rememberSaveable { mutableStateOf(listOf<String>()) }
    var confirming by rememberSaveable { mutableStateOf(false) }
    var menuExpanded by rememberSaveable { mutableStateOf(false) }
    var sortType by rememberSaveable { mutableStateOf(FridgeSortType.CATEGORY) }
    val selected = ingredients.map { it.name }.filter { it in selectedNames }
    val displayedIngredients = remember(ingredients, sortType, appearanceCatalog) {
        sortFridgeIngredients(ingredients, sortType, appearanceCatalog)
    }
    fun cancelSelection() {
        selecting = false
        selectedNames = emptyList()
        confirming = false
    }
    LaunchedEffect(ingredients) {
        selectedNames = selectedNames.filter { name -> ingredients.any { it.name == name } }
        if (ingredients.isEmpty()) cancelSelection()
        if (selectedNames.isEmpty()) confirming = false
    }
    BackHandler(enabled = selecting && !confirming) { if (controlsEnabled) cancelSelection() }

    Box(modifier.fillMaxSize()) {
        Column(Modifier.fillMaxSize().padding(horizontal = 24.dp)) {
            Spacer(Modifier.height(24.dp))
            TitleText(
                text = nickname + " 님의 냉장고",
                color = MaterialTheme.colorScheme.onBackground,
                modifier = Modifier.fillMaxWidth()
            )
            FridgeSortDropdown(selected = sortType, onSelected = { sortType = it })
            if (selecting) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text("${selected.size}개 선택", Modifier.weight(1f), style = MaterialTheme.typography.titleSmall)
                    TextButton(onClick = { selectedNames = ingredients.map { it.name } }, enabled = controlsEnabled) {
                        Text("전체 선택")
                    }
                    TextButton(onClick = ::cancelSelection, enabled = controlsEnabled) { Text("취소") }
                }
                Button(
                    onClick = { confirming = true },
                    enabled = controlsEnabled && selected.isNotEmpty(),
                    modifier = Modifier.fillMaxWidth().testTag("delete-selected-ingredients")
                ) { Text(if (controlsEnabled) "선택한 재료 삭제" else "재료를 삭제하고 있어요") }
            } else {
                Text("재료를 길게 누르면 여러 개를 선택할 수 있어요", style = MaterialTheme.typography.bodySmall)
            }
            Spacer(Modifier.height(12.dp))
            BoxWithConstraints(Modifier.weight(1f).fillMaxWidth()) {
                val areaHeight = maxHeight
                Box(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
                    Box(Modifier.fillMaxWidth().heightIn(min = areaHeight)
                        .clip(RoundedCornerShape(29.dp)).background(MaterialTheme.colorScheme.surfaceVariant)) {
                        FridgeShelves(
                            ingredients = displayedIngredients,
                            catalog = appearanceCatalog,
                            groupedByCategory = sortType == FridgeSortType.CATEGORY,
                            managing = selecting,
                            selectedNames = selected.toSet(),
                            controlsEnabled = controlsEnabled,
                            onRemoveIngredient = { name ->
                                selectedNames = if (name in selectedNames) selectedNames - name else selectedNames + name
                            },
                            onLongPressIngredient = { name ->
                                if (!selecting) {
                                    selecting = true
                                    selectedNames = listOf(name)
                                } else if (name !in selectedNames) selectedNames = selectedNames + name
                            },
                            modifier = Modifier.padding(horizontal = 16.dp).padding(top = 10.dp, bottom = 92.dp)
                        )
                        if (ingredients.isEmpty()) {
                            Text("냉장고가 비었어요", Modifier.align(Alignment.TopCenter).padding(top = 35.dp),
                                style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }
        }
        if (!selecting) {
            Box(Modifier.align(Alignment.BottomEnd).padding(24.dp)) {
                FloatingActionButton(
                    onClick = { if (controlsEnabled) menuExpanded = !menuExpanded },
                    modifier = Modifier.testTag("fridge-actions"),
                    containerColor = MaterialTheme.colorScheme.primary,
                    contentColor = MaterialTheme.colorScheme.onPrimary
                ) {
                    Icon(painterResource(R.drawable.ic_plus), contentDescription = "냉장고 작업 메뉴", modifier = Modifier.size(28.dp))
                }
                DropdownMenu(expanded = menuExpanded, onDismissRequest = { menuExpanded = false }) {
                    DropdownMenuItem(text = { Text("부족한 재료 추천") }, enabled = controlsEnabled, onClick = {
                        menuExpanded = false
                        onSuggestionsClick()
                    })
                    DropdownMenuItem(text = { Text("냉장고 재료 삭제") }, enabled = controlsEnabled && ingredients.isNotEmpty(), onClick = {
                        menuExpanded = false
                        selectedNames = emptyList()
                        selecting = true
                    })
                    DropdownMenuItem(text = { Text("냉장고 재료 추가") }, enabled = controlsEnabled, onClick = {
                        menuExpanded = false
                        onAddIngredientClick()
                    })
                }
            }
        }
    }
    if (confirming && selected.isNotEmpty()) {
        AlertDialog(
            onDismissRequest = { if (controlsEnabled) confirming = false },
            title = { Text("선택한 재료 ${selected.size}개 삭제") },
            text = {
                Column(Modifier.heightIn(max = 280.dp).verticalScroll(rememberScrollState())) {
                    Text(selected.joinToString(", "))
                    Spacer(Modifier.height(12.dp))
                    Text("냉장고에서 선택한 재료를 삭제할까요?")
                }
            },
            confirmButton = {
                TextButton(
                    modifier = Modifier.testTag("confirm-ingredient-delete"),
                    enabled = controlsEnabled,
                    onClick = {
                        confirming = false
                        onRemoveIngredients(selected.toSet(), ::cancelSelection)
                    }
                ) { Text("삭제") }
            },
            dismissButton = {
                TextButton(modifier = Modifier.testTag("cancel-ingredient-delete"),
                    enabled = controlsEnabled, onClick = { confirming = false }) { Text("취소") }
            }
        )
    }
}
