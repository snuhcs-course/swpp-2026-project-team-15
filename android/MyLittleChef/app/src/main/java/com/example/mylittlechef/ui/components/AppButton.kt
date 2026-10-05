package com.example.mylittlechef.ui.components

import android.R.attr.strokeWidth
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.defaultMinSize
import com.example.mylittlechef.R

import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape

import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.TextButton
import androidx.compose.material3.Text

import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment

import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
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

@Composable
fun DashedButton(
    text: String,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
    color: Color = Color.Unspecified
)
{
    Box(
        modifier = modifier
            .defaultMinSize(minHeight = 48.dp)
            .clip(RoundedCornerShape(15.dp))
            .clickable(role = Role.Button, onClick = onClick)
            .border(
                width = 2.dp,
                color = color,
                shape = RoundedCornerShape(15.dp)
            ),
        contentAlignment = Alignment.Center
    )
    {
        Text(
            text = text,
            color = color,
            modifier = Modifier
                .padding(
                    horizontal = 24.dp,
                    vertical = 12.dp
                )
        )
    }
}