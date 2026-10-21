package com.example.mylittlechef.ui.recipe

import androidx.compose.foundation.Image
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
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import com.example.mylittlechef.ui.components.BackButton
import com.example.mylittlechef.ui.components.LikeButton
import com.example.mylittlechef.ui.components.RecipeBodyText
import com.example.mylittlechef.ui.components.RecipeSubtitleText
import com.example.mylittlechef.ui.components.TitleText
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.ui.theme.Gray
import com.example.mylittlechef.viewmodel.UserViewModel

@Composable
fun RecipeDetailScreen(
    user: UserViewModel,
    recipe: Recipe,
    onBackClick: () -> Unit,
    onLikeClick: () -> Unit
)
{
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .background(Color.White)
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

                if (recipe.imageRes != null) {
                    Image(
                        painter = painterResource(recipe.imageRes),
                        contentDescription = recipe.name,
                        modifier = Modifier
                            .width(imageWidth)
                            .height(imageHeight)
                            .clip(RoundedCornerShape(24.dp))
                            .align(Alignment.CenterHorizontally)
                    )
                }
                else {
                    Box(
                        modifier = Modifier
                            .width(imageWidth)
                            .height(imageHeight)
                            .clip(RoundedCornerShape(24.dp))
                            .background(DeepGreen)
                            .align(Alignment.CenterHorizontally)
                    )
                }

                RecipeMeta(recipe.time)
                HorizontalDivider()
                RecipeIngredients(recipe.ingredients)
                HorizontalDivider()
                RecipeSteps(recipe.steps)
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
                color = Color.Black
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
    ingredients: List<Ingredient>
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
            ingredients.forEach { ingredient ->
                IngredientCard(ingredient.name)
            }
        }
    }
}

@Composable
private fun IngredientCard(
    name: String
)
{
    Box(
        modifier = Modifier
            .height(45.dp)
            .clip(RoundedCornerShape(20.dp))
            .background(Gray)
            .padding(
                horizontal = 20.dp,
                vertical = 12.dp
            )
    )
    {
        Text(
            text = name,
            style = MaterialTheme.typography.labelMedium,
            textAlign = TextAlign.Center,
            color = Color.Black
        )
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
