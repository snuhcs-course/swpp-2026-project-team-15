package com.example.mylittlechef.ui.recipe

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.VerticalDivider
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.Dp
import com.example.mylittlechef.model.Recipe
import com.example.mylittlechef.viewmodel.UserViewModel
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.R
import com.example.mylittlechef.ui.components.SubtitleText
import com.example.mylittlechef.ui.components.TitleText
import com.example.mylittlechef.ui.theme.Gray

@Composable
fun RecipeScreen(
    user: UserViewModel,
    onCardClick: (Recipe) -> Unit,
    modifier: Modifier = Modifier
)
{

}

@Composable
fun RecipeContent(
    user: UserViewModel,
    onCardClick: (Recipe) -> Unit,
    modifier: Modifier = Modifier
)
{
    Column(
        modifier = modifier
            .fillMaxSize()
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

        SubtitleText(
            text = "AI가 ${user.nickname} 님의 냉장고를 분석했어요", // TODO: Color tag
            color = Color.Black
        )

        // TODO: Tab and contents
    }
}

@Composable
fun RecipeCard(
    recipe: Recipe,
    onCardClick: (Recipe) -> Unit,
    onLikeClick: (Recipe) -> Unit,
    imageSize: Dp = 96.dp
)
{
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(Gray)
            .clip(RoundedCornerShape(24.dp))
    )
    {
        // like button
        IconButton(
            onClick = {
                onLikeClick(recipe)
            }
        )
        {

        }

        Row(

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
                )
            }

            Column(

            )
            {

            }

            VerticalDivider(

            )

            IconButton(
                onClick = {
                    onCardClick(recipe)
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
    }
}