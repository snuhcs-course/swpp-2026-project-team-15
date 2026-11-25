// Ingredient recipe sheet assisted by Codex, 2026-11-24; human review pending.
package com.example.mylittlechef.ui.fridge

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.domain.Dish
import com.example.mylittlechef.ui.components.*
import com.example.mylittlechef.ui.recipe.RecipeCard
import com.example.mylittlechef.viewmodel.*

@Composable
fun IngredientRecipeSheet(name:String,dishes:DishViewModel,onDishClick:(Dish)->Unit) {
    val related=dishes.relatedToIngredient(name)
    Column(Modifier.fillMaxWidth().heightIn(max=640.dp).testTag("ingredient-recipe-sheet")) {
        Row(Modifier.fillMaxWidth().padding(horizontal=20.dp,vertical=12.dp),
            verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(10.dp)) {
            IngredientBadge(name,size=36.dp)
            Text("${name}로 만드는 요리",style=MaterialTheme.typography.titleMedium,modifier=Modifier.weight(1f))
        }
        Text("현재 추천에서 골랐어요 · 부족한 핵심 재료가 적은 순",Modifier.padding(horizontal=20.dp),
            style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
        Column(Modifier.weight(1f,fill=false).fillMaxWidth().verticalScroll(rememberScrollState()).padding(20.dp),
            verticalArrangement=Arrangement.spacedBy(12.dp)) {
            when(val state=dishes.state) {
                DishUiState.Loading -> IngredientLoading(LoadingTask.DISHES)
                is DishUiState.Error -> {
                    Text(state.message,color=MaterialTheme.colorScheme.error)
                    OutlinedButton(onClick=dishes::retry) {Text("다시 시도")}
                }
                else -> if(related.isEmpty()) {
                    Text("현재 추천에는 이 재료를 활용한 요리가 없어요.")
                    TextButton(onClick=dishes::retry) {Text("다시 추천받기")}
                }
            }
            related.forEach {dish -> RecipeCard(dishes,dish,onDishClick)}
        }
    }
}
