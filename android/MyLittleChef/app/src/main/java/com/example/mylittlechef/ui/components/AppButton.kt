package com.example.mylittlechef.ui.components

import androidx.compose.foundation.layout.PaddingValues
import com.example.mylittlechef.R

import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape

import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.TextButton

import androidx.compose.runtime.Composable

import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp

@Composable
fun NormalButton(
    text: String,
    modifier: Modifier = Modifier,
    buttonColor: Color, // TODO: Color.kt
    textColor: Color, // TODO: Color.kt
    onClick: () -> Unit
)
{
    Button(
        modifier = modifier
            .width(181.dp)
            .height(53.dp),
        colors = ButtonDefaults.buttonColors(
            containerColor = buttonColor
        ),
        onClick = onClick,
        shape = RoundedCornerShape(17.dp)
    )
    {
        NormalButtonText(
            text = text,
            textAlign = TextAlign.Center,
            color = textColor
        )
    }
}

@Composable
fun TextOnlyButton(
    text: String,
    modifier: Modifier = Modifier,
    textColor: Color, // TODO: Color.kt
    onClick: () -> Unit
)
{
    TextButton(
        modifier = modifier,
        onClick = onClick
    )
    {
        TextOnlyButtonText(
            text = text,
            textAlign = TextAlign.Center,
            color = textColor
        )
    }
}

@Composable
fun ToggleButton(
    text: String,
    selected: Boolean,
    modifier: Modifier = Modifier,
    buttonColorOn: Color,
    buttonColorOff: Color,
    textColorOn: Color,
    textColorOff: Color,
    onClick: () -> Unit
)
{
    Button(
        modifier = modifier
            .height(45.dp),
        contentPadding = PaddingValues(
            horizontal = 20.dp,
            vertical = 12.dp
        ),
        colors = ButtonDefaults.buttonColors(
            containerColor = if (selected) buttonColorOn else buttonColorOff
        ),
        onClick = onClick,
        shape = RoundedCornerShape(20.dp)
    )
    {
        NormalButtonText(
            text = text,
            textAlign = TextAlign.Center,
            color = if (selected) textColorOn else textColorOff
        )
    }

}

@Composable
fun BackButton(
    modifier: Modifier = Modifier,
    onClick: () -> Unit
)
{
    IconButton(
        modifier = modifier,
        onClick = onClick
    )
    {
        Icon(
            painter = painterResource(R.drawable.ic_back),
            contentDescription = "back"
        )
    }
}