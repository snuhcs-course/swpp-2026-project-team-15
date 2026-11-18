// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.ui.dish

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.R
import com.example.mylittlechef.domain.Availability
import com.example.mylittlechef.domain.Dish
import com.example.mylittlechef.domain.DishRecipe
import com.example.mylittlechef.domain.RecipeChange
import com.example.mylittlechef.domain.RecipeStep
import com.example.mylittlechef.domain.Revision
import com.example.mylittlechef.ui.components.IngredientBadge
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.ui.theme.Gray
import com.example.mylittlechef.viewmodel.RecipeUiState
import com.example.mylittlechef.viewmodel.ReviseUiState

private const val NOTICE = "AI가 만든 제안이에요. 맛과 알레르기는 직접 확인해 주세요."

/** One ingredient line of either version of the recipe: the icon, the name and the amount. */
private data class Line(val name: String, val amount: String?, val missing: Boolean)

/** The recipe of one dish, then the same recipe revised to the fridge (original and revised side by side as two tabs). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DishRecipeSheet(
    dish: Dish,
    recipe: RecipeUiState?,
    revision: ReviseUiState?,
    onRetryRecipe: () -> Unit,
    onRevise: () -> Unit,
    onDismiss: () -> Unit
) {
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ) {
        Column(
            Modifier.verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).padding(bottom = 16.dp)
                .testTag("recipe-sheet"),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Text(dish.name, style = MaterialTheme.typography.titleLarge, modifier = Modifier.semantics { heading() })
            when (recipe) {
                null, RecipeUiState.Loading -> Loading("레시피를 불러오고 있어요...")
                is RecipeUiState.Error -> ErrorBox(recipe.message, "다시 시도", onRetryRecipe, "recipe-retry")
                is RecipeUiState.Success -> RecipeContent(recipe.recipe, revision, onRevise)
            }
            Text(NOTICE, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun RecipeContent(recipe: DishRecipe, revision: ReviseUiState?, onRevise: () -> Unit) {
    val done = (revision as? ReviseUiState.Done)?.revision as? Revision.Revised
    var showRevised by rememberSaveable(recipe.dishId, done != null) { mutableStateOf(done != null) }
    Caption(attribution(recipe))
    if (done != null) {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            FilterChip(!showRevised, { showRevised = false }, { Text("원본") }, Modifier.testTag("recipe-tab-original"))
            FilterChip(showRevised, { showRevised = true }, { Text("바꾼 레시피") }, Modifier.testTag("recipe-tab-revised"))
        }
    }
    if (done != null && showRevised) {
        Body(
            lines = done.ingredients.map { Line(it.name, it.amount, false) },
            servings = done.servings ?: recipe.servings,
            steps = done.steps,
            tips = done.tips
        )
        Changes(done.changes)
    } else {
        Body(
            lines = recipe.ingredients.map { Line(it.name, it.amount, it.availability == Availability.UNAVAILABLE) },
            servings = recipe.servings,
            steps = recipe.steps,
            tips = recipe.tips
        )
        if (recipe.captionGaps || recipe.uncertain.isNotEmpty()) Uncertain(recipe)
    }
    ReviseAction(recipe, revision, onRevise)
}

private fun attribution(recipe: DishRecipe): String {
    val video = listOfNotNull(recipe.videoChannel, recipe.videoTitle).joinToString(" · ")
    val origin = if (recipe.fromVideo) "AI가 영상을 보고 정리한 레시피" else "AI가 영상의 자막에서 정리한 레시피"
    return if (video.isBlank()) origin else "$origin · $video"
}

@Composable
private fun Body(lines: List<Line>, servings: Int?, steps: List<RecipeStep>, tips: List<String>) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Text("재료", style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f).semantics { heading() })
        if (servings != null) Text("${servings}인분", style = MaterialTheme.typography.labelMedium)
    }
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) { lines.forEach { IngredientLine(it) } }
    Text("순서", style = MaterialTheme.typography.titleMedium, modifier = Modifier.semantics { heading() })
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { steps.forEach { StepLine(it) } }
    if (tips.isNotEmpty()) {
        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
            tips.forEach { Text("· $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
    }
}

@Composable
private fun IngredientLine(line: Line) {
    val state = if (line.missing) "없음" else "있음"
    Row(
        Modifier.fillMaxWidth().semantics(mergeDescendants = true) { contentDescription = "${line.name} ${line.amount.orEmpty()}, $state" },
        verticalAlignment = Alignment.CenterVertically
    ) {
        val badge = if (line.missing) {
            Modifier.alpha(0.4f).border(1.5.dp, MaterialTheme.colorScheme.error, CircleShape)
        } else {
            Modifier
        }
        IngredientBadge(line.name, badge, size = 28.dp)
        Spacer(Modifier.width(10.dp))
        Text(line.name, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
        if (!line.amount.isNullOrBlank()) {
            Text(line.amount, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
    }
}

@Composable
private fun StepLine(step: RecipeStep) {
    Row(verticalAlignment = Alignment.Top) {
        Box(
            Modifier.size(22.dp).background(MaterialTheme.colorScheme.primary, CircleShape),
            contentAlignment = Alignment.Center
        ) { Text("${step.n}", style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onPrimary) }
        Spacer(Modifier.width(10.dp))
        Text(step.text, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
    }
}

@Composable
private fun Changes(changes: List<RecipeChange>) {
    if (changes.isEmpty()) {
        Text("바꿀 것이 없어요. 지금 재료로 그대로 만들 수 있어요.", style = MaterialTheme.typography.bodyMedium, color = DeepGreen)
        return
    }
    Text("바뀐 점", style = MaterialTheme.typography.titleMedium, modifier = Modifier.semantics { heading() })
    Column(
        Modifier.fillMaxWidth().background(Gray, RoundedCornerShape(16.dp)).padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp)
    ) {
        changes.forEach { Text("· ${it.reason}", style = MaterialTheme.typography.bodySmall, modifier = Modifier.testTag("recipe-change")) }
    }
}

@Composable
private fun Uncertain(recipe: DishRecipe) {
    val text = buildString {
        if (recipe.captionGaps) append("자막이 불분명한 부분이 있어요. ")
        if (recipe.uncertain.isNotEmpty()) append("확인이 필요해요: ${recipe.uncertain.joinToString(", ")}")
    }
    Text(text, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.error)
}

@Composable
private fun ReviseAction(recipe: DishRecipe, state: ReviseUiState?, onRevise: () -> Unit) {
    when (state) {
        ReviseUiState.Loading -> Loading("내 재료에 맞게 바꾸고 있어요...")
        is ReviseUiState.Error -> ErrorBox(state.message, "다시 시도", onRevise, "revise-retry")
        is ReviseUiState.Done -> when (val result = state.revision) {
            is Revision.Refused -> Column(
                Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.errorContainer, RoundedCornerShape(16.dp)).padding(12.dp)
                    .testTag("revise-refused"),
                verticalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                Text("지금 재료로는 바꾸기 어려워요", style = MaterialTheme.typography.titleSmall, color = MaterialTheme.colorScheme.onErrorContainer)
                Text(result.reason, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onErrorContainer)
            }
            is Revision.Failed -> ErrorBox(result.message, "다시 시도", onRevise, "revise-retry")
            is Revision.Revised -> Unit
        }
        null -> if (recipe.hasMissing) {
            Button(onClick = onRevise, modifier = Modifier.fillMaxWidth().height(48.dp).testTag("revise-button")) {
                Icon(painterResource(R.drawable.ic_swap), contentDescription = null, modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(8.dp))
                Text("내 재료로 바꾸기")
            }
        } else {
            Text("지금 재료로 그대로 만들 수 있어요", style = MaterialTheme.typography.labelLarge, color = DeepGreen)
        }
    }
}

@Composable
private fun Caption(text: String) {
    Text(text, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
}

@Composable
private fun Loading(text: String) {
    Row(
        Modifier.fillMaxWidth().padding(vertical = 8.dp).semantics { liveRegion = LiveRegionMode.Polite },
        verticalAlignment = Alignment.CenterVertically
    ) {
        CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
        Spacer(Modifier.width(10.dp))
        Text(text, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun ErrorBox(message: String, action: String, onAction: () -> Unit, tag: String) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(message, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.error)
        TextButton(onClick = onAction, modifier = Modifier.testTag(tag)) { Text(action) }
    }
}
