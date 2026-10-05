package com.example.mylittlechef.ui.fridge.components

import androidx.compose.runtime.Composable
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.layout.size
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

import com.example.mylittlechef.model.Ingredient

import com.example.mylittlechef.ui.theme.DeepGreen

@Composable
fun IngredientItem(
    ingredient: Ingredient,
    modifier: Modifier = Modifier,
    imageSize: Dp = 45.dp
)
{
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally
    )
    {
        val imageRes = ingredient.imageRes
        if (imageRes != null) {
            Image(
                painter = painterResource(imageRes),
                contentDescription = ingredient.name,
                modifier = Modifier
                    .size(imageSize)
                    .clip(CircleShape),
                contentScale = ContentScale.Crop
            )
        }
        else {
            Box(
                modifier = Modifier
                    .size(imageSize)
                    .clip(CircleShape)
                    .background(DeepGreen)
            )
        }

        Spacer(Modifier.height(7.dp))

        Text(
            text = ingredient.name,
            style = MaterialTheme.typography.labelSmall,
            color = Color.Black,
            textAlign = TextAlign.Center,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )

    }
}