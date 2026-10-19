package com.example.mylittlechef.ui.recipe

import androidx.compose.foundation.layout.Column
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import com.example.mylittlechef.model.Recipe
import com.example.mylittlechef.viewmodel.RecipeViewModel

@Composable
fun RecipeRequestStatus(recipes: RecipeViewModel, favorites: Boolean, retry: () -> Unit) {
    val error = if (favorites) recipes.favoriteError else recipes.errorMessage
    Column {
        Text("도구·알레르기 적합성은 검증되지 않았어요.")
        if (!favorites && recipes.isLoading) Text("추천과 AI 수정 결과를 불러오는 중이에요.")
        if (error != null) {
            Text(error)
            TextButton(onClick = retry) { Text("다시 시도") }
        } else if (!favorites && !recipes.isLoading && recipes.recommended.isEmpty()) {
            Text("추천할 레시피가 없어요. 냉장고 재료를 추가하거나 수정해 주세요.")
        }
        if (!favorites && recipes.unmapped.isNotEmpty()) {
            Text("추천에 연결하지 못한 재료: ${recipes.unmapped.joinToString(", ")}")
        }
    }
}

@Composable
fun IntegratedRecipeDetail(recipe: Recipe) {
    val original = requireNotNull(recipe.source)
    val revision = recipe.revision
    var showSuggestion by remember(recipe) { mutableStateOf(false) }
    val text = if (showSuggestion) revision?.suggestion ?: original else original
    Column {
        Text("원본과 AI 제안을 구분해 확인해 주세요. 조리 안전성·알레르기는 검증되지 않았어요.")
        Text(when (revision?.status) {
            "revised" -> "AI 수정 제안이 있어요. 검증된 조리법은 아니에요."
            "refused" -> "AI 수정 거절: ${revision.reason}"
            "failed" -> "AI 수정 실패: ${revision.reason}"
            "not_attempted" -> "AI 수정 미시도: ${revision.reason}"
            else -> "저장된 레시피의 원본이에요."
        }, modifier = Modifier.testTag("revision-status"))
        if (revision?.suggestion != null) {
            TextButton(onClick = { showSuggestion = !showSuggestion },
                modifier = Modifier.testTag("recipe-version-toggle")) {
                Text(if (showSuggestion) "원본 보기" else "AI 제안 보기")
            }
        }
        Text(if (showSuggestion) "AI 수정 제안" else "원본 레시피", modifier = Modifier.testTag("recipe-version"))
        Text(text.name)
        Text("${original.cookingTime ?: "시간 미상"} · ${text.servings ?: "인분 미상"}")
        if (showSuggestion) revision?.changes?.forEach { Text(it) }
        HorizontalDivider()
        RecipeIngredients(text.ingredients.map { com.example.mylittlechef.model.Ingredient(it) })
        HorizontalDivider()
        RecipeSteps(text.steps)
    }
}
