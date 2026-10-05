package com.example.mylittlechef.ui.recipe

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
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
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.VerticalDivider
import androidx.compose.runtime.Composable
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
import com.example.mylittlechef.model.Preset
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

@Composable
fun RecipeScreen(
    user: UserViewModel,
    fridge: FridgeViewModel,
    onRecipeCardClick: (Recipe) -> Unit,
    onLikeClick: (Recipe) -> Unit,
    modifier: Modifier = Modifier
)
{
    RecipeContent(
        user,
        fridge,
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
    onRecipeCardClick: (Recipe) -> Unit,
    onLikeClick: (Recipe) -> Unit,
    modifier: Modifier = Modifier
)
{
    Column(
        modifier = modifier
            .fillMaxSize()
            .background(Color.White)
            .padding(
                horizontal = 29.dp
            )
    )
    {
        Spacer(Modifier.height(32.dp))

        TitleText(
            text = "${user.nickname} 님을 위한 레시피예요", // TODO: Color tag
            color = Color.Black
        )

        Spacer(Modifier.height(12.dp))

        SubtitleText(
            text = "AI가 ${user.nickname} 님의 냉장고를 분석했어요", // TODO: Color tag
            color = Color.Black
        )

        var selectedTab by remember {
            mutableStateOf(RecipeTab.RECOMMENDED)
        }
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(
                    top = 16.dp
                )
        )
        {
            RecipeTabButton(
                text = "추천",
                selected = selectedTab == RecipeTab.RECOMMENDED,
                buttonColorOn = DeepGreen,
                buttonColorOff = Color.White,
                textColorOn = Color.Black,
                textColorOff = GreenGray,
                onClick = {
                    selectedTab = RecipeTab.RECOMMENDED
                },
                dividerWidth = 35.dp
            )

            RecipeTabButton(
                text = "즐겨찾기",
                selected = selectedTab == RecipeTab.LIKE,
                buttonColorOn = DeepGreen,
                buttonColorOff = Color.White,
                textColorOn = Color.Black,
                textColorOff = GreenGray,
                onClick = {
                    selectedTab = RecipeTab.LIKE
                },
                dividerWidth = 70.dp
            )
        }

        when (selectedTab) {
            RecipeTab.RECOMMENDED -> {
                RecipeCardList(
                    user = user,
                    fridge = fridge,
                    recipes = Preset.sampleRecipes,
                    onRecipeCardClick = onRecipeCardClick,
                    onLikeClick = onLikeClick
                )
            }
            RecipeTab.LIKE -> {
                RecipeCardList(
                    user = user,
                    fridge = fridge,
                    recipes = Preset.sampleRecipes.filter { it.id in user.likes },
                    onRecipeCardClick = onRecipeCardClick,
                    onLikeClick = onLikeClick
                )
            }
        }
    }
}

@Composable
fun RecipeCardList(
    user: UserViewModel,
    fridge: FridgeViewModel,
    recipes: List<Recipe>,
    onRecipeCardClick: (Recipe) -> Unit,
    onLikeClick: (Recipe) -> Unit
)
{
    // TODO: drop down

    // scroll view
    Box(
        modifier = Modifier
            .fillMaxSize()
            .padding(
                top = 2.dp
            )
    )
    {
        // scroll content
        Box(
            modifier = Modifier
                .fillMaxSize()
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
                Spacer(Modifier.height(24.dp))
                recipes.forEach { recipe ->
                    RecipeCard(
                        user = user,
                        fridge = fridge,
                        recipe = recipe,
                        onRecipeCardClick = onRecipeCardClick,
                        onLikeClick = onLikeClick
                    )
                }
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
    )
    {
        Row(
            modifier = Modifier
                .fillMaxSize(),
            verticalAlignment = Alignment.CenterVertically
        )
        {
            if (recipe.imageRes != null) {
                Image(
                    painter = painterResource(recipe.imageRes),
                    contentDescription = recipe.name,
                    modifier = Modifier
                        .size(imageSize)
                        .clip(RoundedCornerShape(24.dp))
                )
            }
            else {
                Box(
                    modifier = Modifier
                        .size(imageSize)
                        .clip(RoundedCornerShape(24.dp))
                        .background(DeepGreen)
                )
            }

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
                        color = Color.Black
                    )
                }
                Spacer(Modifier.height(10.dp))
                RecipeDescriptionText(
                    fridgeIngredients = fridge.ingredients,
                    recipeIngredients = recipe.ingredients
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
                    tint = Color.Black
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
    recipeIngredients: List<Ingredient>
)
{
    val missingIngredients = recipeIngredients.filter { recipeIngredient ->
        fridgeIngredients.none { fridgeIngredient ->
            fridgeIngredient.name == recipeIngredient.name
        }
    }

    val lastChar = missingIngredients.last().name.last()

    fun hasFinalConsonant(char: Char): Boolean {
        return (char.code - '가'.code) % 28 != 0
    }

    val particle = if (hasFinalConsonant(lastChar)) "이" else "가"

    RecipeBodyText(
        text = if (missingIngredients.isEmpty()) {
            "지금 바로 만들 수 있어요"
        } else {
            "${missingIngredients.joinToString(", ") { "${it.name}" }}${particle} 없어요"
        }
    )
}