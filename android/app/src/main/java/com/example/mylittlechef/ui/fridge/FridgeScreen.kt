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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.R
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.ui.components.TitleText
import com.example.mylittlechef.ui.fridge.components.FridgeShelves
import com.example.mylittlechef.ui.theme.DeepBrown
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.ui.theme.Gray
import com.example.mylittlechef.viewmodel.IngredientSuggestionViewModel
import com.example.mylittlechef.viewmodel.FridgeViewModel
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
    Box(modifier = modifier.fillMaxSize().background(Color.White)) {
        FridgeContent(
            nickname = user.nickname,
            ingredients = fridge.ingredients,
            controlsEnabled = fridge.removingIngredient == null && !fridge.isSavingPantry,
            onRemoveIngredient = fridge::removeIngredient,
            onAddIngredientClick = onAddIngredientClick,
            onSuggestionsClick = { showSuggestions = true }
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
    onRemoveIngredient: (String) -> Unit,
    onAddIngredientClick: () -> Unit,
    onSuggestionsClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    var managing by rememberSaveable { mutableStateOf(false) }
    var pendingName by rememberSaveable { mutableStateOf<String?>(null) }
    LaunchedEffect(ingredients) {
        if (ingredients.isEmpty()) managing = false
        if (pendingName != null && ingredients.none { it.name == pendingName }) pendingName = null
    }
    BackHandler(enabled = managing && pendingName == null) { managing = false }

    Column(modifier.fillMaxSize().padding(horizontal = 29.dp)) {
        Spacer(Modifier.height(32.dp))
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            TitleText(
                text = nickname + " 님의 냉장고",
                color = Color.Black,
                modifier = Modifier.weight(1f)
            )
            TextButton(onClick = onSuggestionsClick, enabled = controlsEnabled) {
                Text("추천", color = DeepGreen)
            }
            TextButton(
                onClick = { managing = !managing },
                enabled = controlsEnabled && ingredients.isNotEmpty()
            ) {
                Text(if (managing) "완료" else "관리", color = DeepGreen)
            }
        }
        Spacer(Modifier.height(18.dp))
        Text(
            text = when {
                !controlsEnabled -> "재료를 삭제하고 있어요"
                managing -> "삭제할 재료의 버튼을 눌러 주세요"
                else -> "재료를 길게 누르면 삭제할 수 있어요"
            },
            style = MaterialTheme.typography.bodySmall
        )
        Spacer(Modifier.height(12.dp))
        BoxWithConstraints(
            modifier = Modifier.weight(1f).fillMaxWidth().padding(horizontal = 6.dp)
        ) {
            val areaHeight = maxHeight
            Box(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
                Box(
                    Modifier.fillMaxWidth().heightIn(min = areaHeight)
                        .clip(RoundedCornerShape(29.dp)).background(Gray)
                ) {
                    FridgeShelves(
                        ingredients = ingredients,
                        managing = managing,
                        controlsEnabled = controlsEnabled,
                        onRemoveIngredient = { pendingName = it },
                        modifier = Modifier.padding(horizontal = 19.dp, vertical = 10.dp)
                    )
                    if (ingredients.isEmpty()) {
                        Text(
                            "냉장고가 비었어요",
                            modifier = Modifier.align(Alignment.TopCenter).padding(top = 35.dp),
                            style = MaterialTheme.typography.bodyMedium
                        )
                    }
                }
            }
            AddIngredientButton(
                onClick = onAddIngredientClick,
                enabled = controlsEnabled,
                modifier = Modifier.align(Alignment.BottomEnd)
            )
        }
    }
    pendingName?.let { selectedName ->
        AlertDialog(
            onDismissRequest = { pendingName = null },
            title = { Text(selectedName + " 삭제") },
            text = { Text("냉장고에서 이 재료를 삭제할까요?") },
            confirmButton = {
                TextButton(
                    modifier = Modifier.testTag("confirm-ingredient-delete"),
                    enabled = controlsEnabled,
                    onClick = {
                        pendingName = null
                        onRemoveIngredient(selectedName)
                    }
                ) { Text("삭제") }
            },
            dismissButton = {
                TextButton(onClick = { pendingName = null }) { Text("취소") }
            }
        )
    }
}

@Composable
private fun AddIngredientButton(
    onClick: () -> Unit,
    enabled: Boolean,
    modifier: Modifier = Modifier
) {
    Button(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier,
        shape = RoundedCornerShape(50),
        colors = ButtonDefaults.buttonColors(containerColor = DeepBrown, contentColor = Color.White),
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 10.dp)
    ) {
        Icon(painterResource(R.drawable.ic_plus), null, modifier = Modifier.size(30.dp))
        Text("재료 추가", style = MaterialTheme.typography.labelLarge,
            textAlign = TextAlign.Left, color = Color.White)
    }
}
