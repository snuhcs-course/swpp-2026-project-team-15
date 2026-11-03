// UI ergonomics and theme changes assisted by Codex, 2026-11-03; human review pending.
// Backend data wiring added with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
// AI-assisted with Codex (GPT-6.1 Sol), 2026-10-14; human review pending.
package com.example.mylittlechef.ui.recipe

import androidx.compose.foundation.layout.heightIn
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.text.style.TextOverflow

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.ui.semantics.Role
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.TextButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.VerticalDivider
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.Dp
import com.example.mylittlechef.model.Recipe
import com.example.mylittlechef.viewmodel.UserViewModel
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.R
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.domain.RecipeSortType
import com.example.mylittlechef.ui.components.LikeButton
import com.example.mylittlechef.ui.components.RecipeBodyText
import com.example.mylittlechef.ui.components.RecipeSubtitleText
import com.example.mylittlechef.ui.components.RecipeTabButton
import com.example.mylittlechef.ui.components.SubtitleText
import com.example.mylittlechef.ui.components.TitleText
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.ui.theme.Gray
import com.example.mylittlechef.ui.theme.GreenGray
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.RecipeViewModel

@Composable
fun RecipeScreen(
    user: UserViewModel,
    fridge: FridgeViewModel,
    recipes: RecipeViewModel,
    onRecipeCardClick: (Recipe) -> Unit,
    onLikeClick: (Recipe) -> Unit,
    modifier: Modifier = Modifier
)
{
    LaunchedEffect(fridge.ingredients, user.allergies, user.utensils) {
        recipes.updateUserContext(fridge.ingredients, user.allergies, user.utensils)
        recipes.refresh(fridge.ingredients)
    }

    RecipeContent(
        user,
        fridge,
        recipes,
        onRecipeCardClick,
        onLikeClick
    )
}

enum class RecipeTab {
    RECOMMENDED,
    LIKE
}

@Composable
fun RecipeContent(
    user: UserViewModel,
    fridge: FridgeViewModel,
    recipes: RecipeViewModel,
    onRecipeCardClick: (Recipe) -> Unit,
    onLikeClick: (Recipe) -> Unit,
    modifier: Modifier = Modifier
) {
    var selectedTab by rememberSaveable { mutableStateOf(RecipeTab.RECOMMENDED) }
    var showInfo by remember { mutableStateOf(false) }
    Box(modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        Column(Modifier.fillMaxSize().padding(horizontal=20.dp)) {
            Row(Modifier.fillMaxWidth().padding(top=12.dp),verticalAlignment=Alignment.CenterVertically) {
                Text("${user.nickname} 님의 레시피",style=MaterialTheme.typography.titleLarge,
                    color=MaterialTheme.colorScheme.onBackground,modifier=Modifier.weight(1f))
                IconButton(onClick={showInfo=true},modifier=Modifier.testTag("recipe-info")
                    .semantics { contentDescription="레시피 안내" }) {
                    Text("ⓘ",style=MaterialTheme.typography.headlineSmall,color=MaterialTheme.colorScheme.primary)
                }
            }
            Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically) {
                RecipeTabButton(text="추천",selected=selectedTab==RecipeTab.RECOMMENDED,
                    buttonColorOn=DeepGreen,buttonColorOff=MaterialTheme.colorScheme.background,
                    textColorOn=MaterialTheme.colorScheme.onBackground,textColorOff=MaterialTheme.colorScheme.onSurfaceVariant,
                    onClick={selectedTab=RecipeTab.RECOMMENDED},dividerWidth=35.dp)
                RecipeTabButton(text="즐겨찾기",selected=selectedTab==RecipeTab.LIKE,
                    buttonColorOn=DeepGreen,buttonColorOff=MaterialTheme.colorScheme.background,
                    textColorOn=MaterialTheme.colorScheme.onBackground,textColorOff=MaterialTheme.colorScheme.onSurfaceVariant,
                    onClick={selectedTab=RecipeTab.LIKE},dividerWidth=70.dp)
                Spacer(Modifier.weight(1f))
                RecipeSortDropdown(recipes.sortType,recipes::selectSort)
            }
            if (recipes.isLoading) Text("레시피를 불러오고 있어요…",style=MaterialTheme.typography.bodySmall)
            recipes.error?.let { failure ->
                Row(verticalAlignment=Alignment.CenterVertically) {
                    Text(failure,modifier=Modifier.weight(1f),style=MaterialTheme.typography.bodySmall)
                    TextButton(onClick={recipes.refresh(fridge.ingredients)}) {Text("다시 시도")}
                }
            }
            recipes.batchRevisionMessage?.let { message ->
                TextButton(onClick={showInfo=true}) {
                    Text(message,maxLines=2,overflow=TextOverflow.Ellipsis,style=MaterialTheme.typography.bodySmall)
                }
            }
            val visible=if(selectedTab==RecipeTab.RECOMMENDED) recipes.sortedRecommended(fridge.ingredients)
                else recipes.liked(user.likes,fridge.ingredients)
            if(!recipes.isLoading && recipes.error==null && visible.isEmpty()) {
                Text(if(selectedTab==RecipeTab.LIKE) "즐겨찾기한 레시피가 없어요." else "현재 재료로 추천할 레시피가 없어요.")
            }
            Box(Modifier.weight(1f)) {
                RecipeCardList(user,fridge,visible,recipes.sortType,recipes::selectSort,onRecipeCardClick,onLikeClick,showSort=false)
            }
        }
        if(recipes.supportsBatchRevision && selectedTab==RecipeTab.RECOMMENDED) {
            Button(onClick=recipes::requestBatchRevision,enabled=recipes.canRequestBatchRevision,
                modifier=Modifier.align(Alignment.BottomEnd).padding(end=20.dp,bottom=12.dp)
                    .heightIn(min=56.dp).shadow(6.dp,RoundedCornerShape(18.dp)),
                shape=RoundedCornerShape(18.dp),colors=ButtonDefaults.buttonColors()) {
                Text("✦  ")
                Text(if(recipes.batchRevisionLoading) "AI 제안을 만들고 있어요…" else "AI 레시피 제안 받기")
            }
        }
    }
    if(showInfo) {
        AlertDialog(onDismissRequest={showInfo=false},title={Text("레시피 안내")},text={
            Column(Modifier.verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(12.dp)) {
                Text("보유 재료를 기준으로 레시피를 골랐어요. 일부 기본 조미료는 서버에서 보유한 것으로 가정해요. 재료 수량은 직접 확인해 주세요.")
                Text("AI 제안은 버튼을 눌렀을 때만 요청해요. 서버가 수정할 레시피를 선택하며, 특정 요리를 지정하는 기능은 아직 지원하지 않아요. 원본과 AI 제안은 상세 화면에서 비교할 수 있어요.")
                Text("현재 서버 요청에는 알레르기·조리도구 조건이 반영되지 않아요. 재료와 조리법을 직접 확인해 주세요.")
                Text("AI 제안은 현재 앱 실행 중 같은 재고에서 재사용해요. 재고나 사용자 조건이 바뀌면 다시 요청해야 해요.")
                recipes.batchRevisionMessage?.let { Text("최근 AI 요청 결과\n$it") }
            }
        },confirmButton={TextButton(onClick={showInfo=false}) {Text("확인")}})
    }
}

@Composable
fun RecipeCardList(
    user: UserViewModel,
    fridge: FridgeViewModel,
    recipes: List<Recipe>,
    sortType: RecipeSortType,
    onSortSelected: (RecipeSortType) -> Unit,
    onRecipeCardClick: (Recipe) -> Unit,
    onLikeClick: (Recipe) -> Unit,
    showSort: Boolean = true
)
{
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(
                top = 2.dp
            )
    )
    {
        if (showSort) RecipeSortDropdown(
            selected = sortType,
            onSelected = onSortSelected,
            modifier = Modifier.align(Alignment.End)
        )
        // scroll content
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .weight(1f)
                .verticalScroll(rememberScrollState())
        )
        {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(
                        start = 8.dp,
                        end = 8.dp
                    ),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            )
            {
                Spacer(Modifier.height(8.dp))
                recipes.forEach { recipe ->
                    RecipeCard(
                        user = user,
                        fridge = fridge,
                        recipe = recipe,
                        onRecipeCardClick = onRecipeCardClick,
                        onLikeClick = onLikeClick
                    )
                }
                Spacer(Modifier.height(88.dp))
            }
        }
    }
}

@Composable
fun RecipeCard(
    user: UserViewModel,
    fridge: FridgeViewModel,
    recipe: Recipe,
    onRecipeCardClick: (Recipe) -> Unit,
    onLikeClick: (Recipe) -> Unit,
    imageSize: Dp = 96.dp
)
{
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(24.dp))
            .background(Gray)
            .testTag("recipe-card-${recipe.id}")
            .clickable(role=Role.Button,onClickLabel="레시피 상세 보기") { onRecipeCardClick(recipe) }
    )
    {
        Row(
            modifier = Modifier
                .fillMaxSize(),
            verticalAlignment = Alignment.CenterVertically
        )
        {
            RecipeImage(recipe, Modifier.size(imageSize).clip(RoundedCornerShape(24.dp)).testTag("recipe-image-${recipe.id}"))

            Spacer(Modifier.weight(0.1f))

            Column(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxHeight()
            )
            {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                )
                {
                    RecipeSubtitleText(recipe.name)
                    Spacer(Modifier.weight(1f))
                    Text(
                        text = "${recipe.time}분",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
                Spacer(Modifier.height(10.dp))
                Text(
                    when {
                        recipe.revisionAvailable -> "✦ AI 제안 있음"
                        recipe.revisionCandidate -> "✦ AI 조정 후보"
                        !recipe.availabilityKnown -> "재고 조건을 다시 확인해 주세요"
                        recipe.missing?.isEmpty() == true -> "✓ 보유 재료로 조리 가능"
                        else -> "추가 재료 확인"
                    }, color = if (recipe.revisionCandidate || recipe.revisionAvailable) MaterialTheme.colorScheme.tertiary else DeepGreen,
                    style = MaterialTheme.typography.labelMedium
                )
                if (recipe.availabilityKnown) RecipeDescriptionText(
                    fridgeIngredients = fridge.ingredients,
                    recipeIngredients = recipe.ingredients,
                    serverMissing = recipe.missing
                )
            }

            Spacer(Modifier.weight(0.05f))

            VerticalDivider(
                thickness = 1.dp,
                color = GreenGray
            )

            IconButton(
                onClick = {
                    onRecipeCardClick(recipe)
                }
            )
            {
                Icon(
                    painter = painterResource(R.drawable.ic_more),
                    contentDescription = "more",
                    tint = MaterialTheme.colorScheme.onSurface
                )
            }

        }

        // like button
        LikeButton(
            selected = recipe.id in user.likes,
            onClick = {
                if (recipe.id in user.likes) {
                    user.removeLikes(recipe.id)
                }
                else {
                    user.addLikes(recipe.id)
                }
            },
            modifier = Modifier.align(Alignment.TopStart)
        )
    }
}

@Composable
private fun RecipeDescriptionText(
    fridgeIngredients: List<Ingredient>,
    recipeIngredients: List<Ingredient>,
    serverMissing: List<Ingredient>?
)
{
    val missingIngredients = serverMissing ?: recipeIngredients.filter { recipeIngredient ->
        fridgeIngredients.none { fridgeIngredient ->
            fridgeIngredient.name == recipeIngredient.name
        }
    }

    RecipeBodyText(
        text = if (missingIngredients.isEmpty()) {
            "지금 바로 만들 수 있어요"
        } else {
            val names = missingIngredients.take(2).joinToString(", ") { it.name }
            val rest = missingIngredients.size - 2
            "부족한 재료 ${missingIngredients.size}개 · $names" + if (rest > 0) " 외 ${rest}개" else ""
        }
    )
}
