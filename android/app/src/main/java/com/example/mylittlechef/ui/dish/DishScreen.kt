// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.ui.dish

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.domain.Dish
import com.example.mylittlechef.domain.DishAdaptation
import com.example.mylittlechef.domain.DishSort
import com.example.mylittlechef.ui.components.IngredientBadge
import com.example.mylittlechef.viewmodel.AdaptUiState
import com.example.mylittlechef.viewmodel.DishUiState
import com.example.mylittlechef.viewmodel.DishViewModel
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.UserViewModel

/** The recipe tab: dishes the fridge can make or nearly make, with videos and substitutions. */
@Composable
fun DishScreen(
    user: UserViewModel,
    fridge: FridgeViewModel,
    dishes: DishViewModel,
    modifier: Modifier = Modifier
) {
    val names = fridge.ingredients.map { it.name }
    LaunchedEffect(names) { dishes.onFridgeChanged(names) }

    Column(modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).padding(horizontal = 20.dp)) {
        Text(
            "${user.nickname} 님의 요리",
            style = MaterialTheme.typography.titleLarge,
            color = MaterialTheme.colorScheme.onBackground,
            modifier = Modifier.padding(top = 12.dp)
        )
        Box(Modifier.padding(top = 8.dp)) { DishSortDropdown(dishes.sort, dishes::selectSort) }
        Spacer(Modifier.height(8.dp))
        when (val state = dishes.state) {
            DishUiState.EmptyFridge -> Message(
                "냉장고가 비어 있어요",
                "재료를 추가하면 만들 수 있는 요리와 영상을 추천해 드려요."
            )
            DishUiState.Loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    CircularProgressIndicator()
                    Spacer(Modifier.height(12.dp))
                    Text("요리를 찾고 있어요...", style = MaterialTheme.typography.bodyMedium)
                }
            }
            DishUiState.NoMatch -> Message(
                "추천할 요리를 찾지 못했어요",
                "재료를 더 추가한 뒤 다시 확인해 보세요.",
                actionLabel = "다시 시도",
                onAction = dishes::retry
            )
            is DishUiState.Error -> Message(
                "요리를 불러오지 못했어요",
                state.message,
                actionLabel = "다시 시도",
                onAction = dishes::retry
            )
            is DishUiState.Success -> DishList(state, dishes)
        }
    }

    val selected = (dishes.state as? DishUiState.Success)?.dishes?.firstOrNull { it.id == dishes.selectedDishId }
    if (selected != null) DishVideoSheet(selected, onDismiss = { dishes.selectDish(null) })
}

@Composable
private fun DishList(state: DishUiState.Success, dishes: DishViewModel) {
    LazyColumn(verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.testTag("dish-list")) {
        if (state.source == "rules") {
            item {
                Text(
                    "AI 연결이 어려워 재료가 겹치는 순서로 보여 드려요.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
        items(state.dishes, key = { it.id }) { dish ->
            DishCard(dish, dishes.adaptState(dish.id), onVideos = { dishes.selectDish(dish.id) }, onAdapt = { dishes.requestAdapt(dish) })
        }
        item { Spacer(Modifier.height(16.dp)) }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun DishCard(dish: Dish, adapt: AdaptUiState?, onVideos: () -> Unit, onAdapt: () -> Unit) {
    Surface(
        shape = RoundedCornerShape(20.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
        modifier = Modifier.fillMaxWidth().testTag("dish-${dish.id}")
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    dish.name,
                    style = MaterialTheme.typography.titleMedium,
                    modifier = Modifier.weight(1f, fill = false)
                )
                if (dish.category.isNotBlank()) {
                    Spacer(Modifier.width(8.dp))
                    Chip(dish.category, MaterialTheme.colorScheme.secondaryContainer, MaterialTheme.colorScheme.onSecondaryContainer)
                }
            }
            Spacer(Modifier.height(6.dp))
            Text(
                if (dish.missing.isEmpty()) "지금 바로 만들 수 있어요" else "부족한 재료 ${dish.missing.size}개",
                style = MaterialTheme.typography.bodyMedium,
                color = if (dish.missing.isEmpty()) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.error
            )
            if (dish.have.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    dish.have.forEach { name -> HaveChip(name) }
                }
            }
            if (dish.missing.isNotEmpty()) {
                Spacer(Modifier.height(6.dp))
                FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    dish.missing.forEach { name ->
                        Chip(
                            "$name · 부족",
                            MaterialTheme.colorScheme.errorContainer,
                            MaterialTheme.colorScheme.onErrorContainer
                        )
                    }
                }
            }
            if (dish.reason.isNotBlank()) {
                Spacer(Modifier.height(8.dp))
                Text(dish.reason, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = onVideos, modifier = Modifier.testTag("dish-videos-${dish.id}")) {
                    Text(if (dish.videos.isEmpty()) "영상 찾기" else "영상 보기 (${dish.videos.size})")
                }
                if (dish.missing.isNotEmpty()) {
                    OutlinedButton(
                        onClick = onAdapt,
                        enabled = adapt !is AdaptUiState.Loading,
                        modifier = Modifier.testTag("dish-adapt-${dish.id}")
                    ) { Text("부족한 재료 대체 보기") }
                }
            }
            when (adapt) {
                null -> Unit
                AdaptUiState.Loading -> Row(Modifier.padding(top = 10.dp), verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(Modifier.height(20.dp).width(20.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(8.dp))
                    Text("대체할 방법을 찾고 있어요...", style = MaterialTheme.typography.bodySmall)
                }
                is AdaptUiState.Error -> Column(Modifier.padding(top = 10.dp)) {
                    Text(adapt.message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                    OutlinedButton(onClick = onAdapt) { Text("다시 시도") }
                }
                is AdaptUiState.Success -> AdaptationBox(adapt.adaptation)
            }
        }
    }
}

@Composable
private fun AdaptationBox(adaptation: DishAdaptation) {
    Column(
        Modifier.padding(top = 10.dp).fillMaxWidth().clip(RoundedCornerShape(12.dp))
            .background(MaterialTheme.colorScheme.surface).padding(12.dp)
    ) {
        Text("AI 제안", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
        if (adaptation.substitutions.isEmpty() && adaptation.skipOk.isEmpty()) {
            Text("대체할 방법을 찾지 못했어요.", style = MaterialTheme.typography.bodySmall)
        }
        adaptation.substitutions.forEach { s ->
            Spacer(Modifier.height(4.dp))
            Text("${s.missing} → ${s.suggestion}", style = MaterialTheme.typography.bodyMedium)
            if (s.uses.isNotEmpty()) {
                Text(
                    "냉장고에서 사용: ${s.uses.joinToString(", ")}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
        if (adaptation.skipOk.isNotEmpty()) {
            Spacer(Modifier.height(4.dp))
            Text("없어도 괜찮아요: ${adaptation.skipOk.joinToString(", ")}", style = MaterialTheme.typography.bodyMedium)
        }
        if (adaptation.note.isNotBlank()) {
            Spacer(Modifier.height(4.dp))
            Text(adaptation.note, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.height(6.dp))
        Text(
            "AI가 만든 제안이에요. 맛과 알레르기는 직접 확인해 주세요.",
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
private fun HaveChip(name: String) {
    Row(
        Modifier.clip(RoundedCornerShape(50)).background(MaterialTheme.colorScheme.surface).padding(end = 10.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        IngredientBadge(name, size = 24.dp)
        Spacer(Modifier.width(6.dp))
        Text(name, style = MaterialTheme.typography.labelMedium)
    }
}

@Composable
private fun Chip(text: String, container: androidx.compose.ui.graphics.Color, content: androidx.compose.ui.graphics.Color) {
    Text(
        text,
        style = MaterialTheme.typography.labelMedium,
        color = content,
        modifier = Modifier.clip(RoundedCornerShape(50)).background(container).padding(horizontal = 10.dp, vertical = 4.dp)
    )
}

@Composable
private fun Message(title: String, body: String, actionLabel: String? = null, onAction: () -> Unit = {}) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(24.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            Text(body, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (actionLabel != null) {
                Spacer(Modifier.height(16.dp))
                Button(onClick = onAction, modifier = Modifier.testTag("dish-retry")) { Text(actionLabel) }
            }
        }
    }
}

@Composable
private fun DishSortDropdown(selected: DishSort, onSelected: (DishSort) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        OutlinedButton(onClick = { expanded = true }, border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline)) {
            Text("정렬: ${selected.label} ⌄", maxLines = 1)
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DishSort.entries.forEach { type ->
                DropdownMenuItem(text = { Text(type.label) }, onClick = { onSelected(type); expanded = false })
            }
        }
    }
}
