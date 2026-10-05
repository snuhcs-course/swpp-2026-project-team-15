package com.example.mylittlechef.ui.fridge

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.ui.components.TitleText
import com.example.mylittlechef.ui.fridge.components.FridgeShelves

import com.example.mylittlechef.ui.theme.Gray
import com.example.mylittlechef.ui.theme.DeepBrown
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.R

@Composable
fun FridgeScreen(
    onAddIngredientClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    // TODO: FridgeViewModel + UI State

    val ingredients = remember { sampleIngredients }

    FridgeContent(
        nickname = "가나다",
        ingredients = ingredients,
        onAddIngredientClick = onAddIngredientClick,
        modifier = modifier
            .background(color = Color.White)
    )
}

@Composable
private fun FridgeContent(
    nickname: String,
    ingredients: List<Ingredient>,
    onAddIngredientClick: () -> Unit,
    modifier: Modifier = Modifier
)
{
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 29.dp)
    )
    {
        Spacer(Modifier.height(32.dp))

        TitleText(
            text = "$nickname 님의 냉장고", // TODO: Color tag
            color = Color.Black
        )

        Spacer(Modifier.height(30.dp))

        BoxWithConstraints(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .padding(horizontal = 6.dp)
        )
        {
            val areaHeight = maxHeight

            // scroll viewport
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .verticalScroll(rememberScrollState())
            )
            {
                // scroll content
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = areaHeight)
                        .clip(RoundedCornerShape(29.dp))
                        .background(Gray)
                )
                {
                    FridgeShelves(
                        ingredients = ingredients,
                        modifier = Modifier
                            .padding(horizontal = 19.dp, vertical = 10.dp)
                    )
                }
            }

            AddIngredientButton(
                onClick = onAddIngredientClick,
                modifier = Modifier
                    .align(Alignment.BottomEnd)
            )
        }
    }
}

@Composable
private fun AddIngredientButton(
    onClick: () -> Unit,
    modifier: Modifier = Modifier
)
{
    Button(
        onClick = onClick,
        modifier = modifier,
        shape = RoundedCornerShape(50),
        colors = ButtonDefaults.buttonColors(
            containerColor = DeepBrown,
            contentColor = Color.White
        ),
        contentPadding = PaddingValues(
            horizontal = 20.dp,
            vertical = 10.dp
        )
    )
    {
        Icon(
            painter = painterResource(R.drawable.ic_plus),
            contentDescription = null,
            modifier = Modifier.size(30.dp)
        )
        Text(
            text = "재료 추가",
            style = MaterialTheme.typography.labelLarge,
            textAlign = TextAlign.Left,
            color = Color.White
        )
    }
}

// ─────────────────────────────────────────────
// 더미 데이터와 미리보기
// ─────────────────────────────────────────────
private val sampleIngredients = listOf(
    Ingredient("다진마늘"),
    Ingredient("고춧가루"),
    Ingredient("소금"),
    Ingredient("양파"),
    Ingredient("두부"),
    Ingredient("김치")
)