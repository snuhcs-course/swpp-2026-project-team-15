// Cached deployed batch suggestions assisted by Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui.recipe

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import com.example.mylittlechef.viewmodel.RevisionUiState
import com.example.mylittlechef.viewmodel.RevisionStatus
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import com.example.mylittlechef.ui.components.BackButton
import com.example.mylittlechef.ui.components.LikeButton
import com.example.mylittlechef.ui.components.RecipeBodyText
import com.example.mylittlechef.ui.components.RecipeSubtitleText
import com.example.mylittlechef.ui.components.TitleText
import com.example.mylittlechef.ui.components.IngredientBadge
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.ui.theme.Gray
import com.example.mylittlechef.viewmodel.UserViewModel

@Composable
fun RecipeDetailScreen(
    user: UserViewModel,
    recipe: Recipe,
    onBackClick: () -> Unit,
    onLikeClick: () -> Unit,
    revisionState: RevisionUiState = RevisionUiState(),
    onRequestRevision: (() -> Unit)? = null,
    batchRevision: Boolean = false
)
{
    var showSuggestion by rememberSaveable(recipe.id) { mutableStateOf(false) }
    val shown = if (showSuggestion && revisionState.status == RevisionStatus.REVISED) revisionState.recipe ?: recipe else recipe
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.background)
    )
    {
        // header
        RecipeDetailHeader(
            user = user,
            recipe = recipe,
            onBackClick = onBackClick,
            onLikeClick = onLikeClick
        )

        // scroll viewport
        Box(
            modifier = Modifier
                .fillMaxSize()
                .navigationBarsPadding()
                .verticalScroll(rememberScrollState())
        )
        {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(
                        start = 24.dp,
                        end = 24.dp
                    ),
                verticalArrangement = Arrangement.spacedBy(17.dp)
            )
            {
                val imageWidth = 272.dp
                val imageHeight = 170.dp

                RecipeImage(recipe, Modifier.width(imageWidth).height(imageHeight)
                    .clip(RoundedCornerShape(24.dp)).align(Alignment.CenterHorizontally))

                RecipeMeta(recipe.time)
                recipe.servingText?.let { Text("원본 분량: $it") }
                if (onRequestRevision != null) {
                    Text(if (shown === recipe) "원본 레시피" else "AI 수정 제안", style = MaterialTheme.typography.titleMedium)
                    Text(if (batchRevision) "AI 요청은 목록의 ‘AI 레시피 제안 받기’에서 해 주세요. 서버가 수정할 레시피를 선택해요."
                        else "원본을 보고 재료를 추가로 준비하거나 AI 조정을 요청할 수 있어요.")
                    if (!recipe.availabilityKnown) Text("원본의 재료 보유 조건을 다시 확인해 주세요.")
                    if ((batchRevision && revisionState.status == RevisionStatus.REVISED) ||
                        (!batchRevision && recipe.availabilityKnown && recipe.revisionCandidate)) {
                        OutlinedButton(
                            enabled = revisionState.status != RevisionStatus.LOADING,
                            onClick = {
                                if (showSuggestion && revisionState.status == RevisionStatus.REVISED) showSuggestion = false
                                else { showSuggestion = true; if (!batchRevision) onRequestRevision() }
                            }
                        ) {
                            Text(when {
                                revisionState.status == RevisionStatus.LOADING -> "AI 제안을 만들고 있어요…"
                                showSuggestion && revisionState.status == RevisionStatus.REVISED -> "원본 보기"
                                revisionState.status == RevisionStatus.ERROR -> "AI 제안 다시 시도"
                                else -> "AI 제안 보기"
                            })
                        }
                    }
                    if (batchRevision && revisionState.status in listOf(RevisionStatus.REFUSED, RevisionStatus.ERROR)) {
                        revisionState.message?.let { Text(it) }
                    }
                    if (showSuggestion) {
                        revisionState.message?.takeIf { it.isNotBlank() }?.let { Text(it) }
                        if (revisionState.status == RevisionStatus.REVISED) {
                            Text(shown.name)
                            shown.servingText?.let { Text("제안 분량: $it") }
                            revisionState.changes.forEach { Text("• $it") }
                            Text("AI 제안은 재료와 조리법을 직접 확인해 주세요. 조리 시간은 원본 기준이에요.")
                        }
                    }
                    Text("현재 AI 요청에는 알레르기·조리도구 조건이 반영되지 않아요.", style = MaterialTheme.typography.bodySmall)
                }
                val missing = if (recipe.availabilityKnown) shown.missing.orEmpty().map { it.name }.toSet() else emptySet()
                if (recipe.availabilityKnown && missing.isNotEmpty()) {
                    Text("부족한 재료: ${missing.joinToString(", ")}", color = MaterialTheme.colorScheme.error)
                }
                HorizontalDivider()
                RecipeIngredients(shown.ingredients, shown.ingredientQuantities, missing)
                HorizontalDivider()
                RecipeSteps(shown.steps)
            }
        }
    }
}

@Composable
fun RecipeDetailHeader(
    user: UserViewModel,
    recipe: Recipe,
    onBackClick: () -> Unit,
    onLikeClick: () -> Unit,
    modifier: Modifier = Modifier
)
{
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .statusBarsPadding()
            .padding(
                bottom = 16.dp
            )
    )
    {
        BackButton(
            onClick = onBackClick
        )
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .padding(
                    horizontal = 16.dp
                )
        )
        {
            TitleText(
                text = recipe.name,
                modifier = Modifier
                    .fillMaxWidth()
                    .align(Alignment.Center)
                    .padding(
                        horizontal = 24.dp
                    ),
                textAlign = TextAlign.Center,
                color = MaterialTheme.colorScheme.onSurface
            )

            LikeButton(
                selected = recipe.id in user.likes,
                onClick = {
                    if (recipe.id in user.likes) {
                        user.removeLikes(recipe.id)
                    }
                    else {
                        user.addLikes(recipe.id)
                    }
                    onLikeClick()
                },
                modifier = Modifier
                    .align(Alignment.CenterEnd)
            )
        }
    }
}

@Composable
fun RecipeMeta(
    time: Int
)
{
    // TODO: Recipe servings

    Row(
        modifier = Modifier.fillMaxWidth()
    )
    {
        RecipeBodyText("${time}분")
    }
}

@Composable
fun RecipeIngredients(
    ingredients: List<Ingredient>,
    quantities: List<String?> = emptyList(),
    missingNames: Set<String> = emptySet()
)
{
    Column(
        modifier = Modifier.fillMaxWidth()
    )
    {
        RecipeSubtitleText("재료")
        FlowRow(
            modifier = Modifier
                .fillMaxWidth()
                .padding(
                    horizontal = 8.dp,
                    vertical = 17.dp
                ),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        )
        {
            ingredients.forEachIndexed { index, ingredient ->
                val label = ingredient.name + quantities.getOrNull(index)?.takeIf { it.isNotBlank() }?.let { " $it" }.orEmpty()
                IngredientCard(label + if (ingredient.name in missingNames) " · 부족" else "", ingredient.name in missingNames,ingredient.name)
            }
        }
    }
}

@Composable
private fun IngredientCard(
    name: String,
    missing: Boolean = false,
    ingredientName: String = name
)
{
    Box(
        modifier = Modifier
            .heightIn(min = 45.dp)
            .clip(RoundedCornerShape(20.dp))
            .background(if (missing) MaterialTheme.colorScheme.errorContainer else Gray)
            .padding(
                    horizontal = 12.dp,
                    vertical = 8.dp
            )
    )
    {
        Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(8.dp)) {
        IngredientBadge(ingredientName,size=32.dp)
        Text(
            text = name,
            style = MaterialTheme.typography.labelMedium,
            textAlign = TextAlign.Center,
            color = if(missing) MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onSurface
        )
        }
    }
}

// TODO: Recipe AI edited

@Composable
fun RecipeSteps(
    steps: List<String>
)
{
    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(17.dp)
    )
    {
        RecipeSubtitleText("조리 방법")
        steps.forEachIndexed { i, step ->
            RecipeBodyText("${(i+1)}. ${step}")
        }
    }
}
