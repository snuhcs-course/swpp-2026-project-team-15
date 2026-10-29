// Ingredient suggestion UI added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
package com.example.mylittlechef.ui.fridge

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.ui.theme.Gray
import com.example.mylittlechef.viewmodel.IngredientSuggestionViewModel

@Composable
fun IngredientSuggestionSheet(
    suggestions: IngredientSuggestionViewModel,
    onRetry: () -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 28.dp, vertical = 16.dp)
    ) {
        Text("식재료 추천", style = MaterialTheme.typography.headlineSmall, color = Color.Black)
        Spacer(Modifier.height(8.dp))
        Text(
            "지금 냉장고에 해당 재료를 더했을 때 바로 만들 수 있는 요리가 많은 순서예요.",
            style = MaterialTheme.typography.bodyMedium
        )
        Spacer(Modifier.height(20.dp))
        when {
            suggestions.isLoading -> Text("추천을 계산 중…")
            suggestions.error != null -> {
                Text(suggestions.error!!)
                Spacer(Modifier.height(8.dp))
                OutlinedButton(onClick = onRetry) { Text("다시 시도") }
            }
            suggestions.suggestions.isEmpty() -> Text("추천할 식재료가 아직 없어요.")
            else -> suggestions.suggestions.forEach { suggestion ->
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(bottom = 10.dp)
                        .background(Gray, RoundedCornerShape(16.dp))
                        .padding(16.dp)
                ) {
                    Text(
                        suggestion.name,
                        style = MaterialTheme.typography.titleMedium,
                        color = DeepGreen
                    )
                    Spacer(Modifier.height(4.dp))
                    Text(
                        "추가하면 바로 만들 수 있는 요리 ${suggestion.readyRecipeCount}개",
                        style = MaterialTheme.typography.bodyMedium
                    )
                    Text(
                        "이 재료가 들어가는 전체 레시피 ${suggestion.recipeCount}개",
                        style = MaterialTheme.typography.bodyMedium
                    )
                    if (suggestion.readyRecipeNames.isNotEmpty()) {
                        Spacer(Modifier.height(4.dp))
                        Text(
                            "예: ${suggestion.readyRecipeNames.joinToString(", ")}",
                            style = MaterialTheme.typography.bodySmall
                        )
                    }
                }
            }
        }
        Spacer(Modifier.height(8.dp))
        Text(
            "현재 서버가 기본 보유로 가정하는 조미료를 포함해 계산해요. 전체 레시피에는 다른 부족한 재료가 있을 수 있어요. 조리도구와 알레르기 조건은 아직 이 숫자에 반영되지 않아요.",
            style = MaterialTheme.typography.bodySmall,
            color = Color.DarkGray
        )
        Spacer(Modifier.height(20.dp))
    }
}
