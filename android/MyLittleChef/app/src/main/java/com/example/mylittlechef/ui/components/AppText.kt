package com.example.mylittlechef.ui.components

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember

import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.withStyle

@Composable
fun TitleText(
    text: String,
    modifier: Modifier = Modifier,
    textAlign: TextAlign? = null,
    color: Color, // TODO: Color.kt
    overflow: TextOverflow = TextOverflow.Clip
)
{
    BaseText(
        text = text,
        style = MaterialTheme.typography.headlineMedium,
        modifier = modifier,
        textAlign = textAlign,
        color = color,
        overflow = overflow
    )
}

@Composable
fun ButtonText(
    text: String,
    modifier: Modifier = Modifier,
    textAlign: TextAlign? = null,
    color: Color, // TODO: Color.kt
    overflow: TextOverflow = TextOverflow.Clip
)
{
    BaseText(
        text = text,
        style = MaterialTheme.typography.labelMedium,
        modifier = modifier,
        textAlign = textAlign,
        color = color,
        overflow = overflow
    )
}

@Composable
private fun BaseText(
    text: String,
    style: TextStyle,
    modifier: Modifier,
    textAlign: TextAlign?,
    color: Color,
    overflow: TextOverflow
)
{
    val parsed = remember(text) {
        parseText(text)
    }

    Text(
        text = parsed,
        style = style,
        modifier = modifier,
        textAlign = textAlign,
        color = color,
        overflow = overflow
    )
}

private val COLOR_REGEX =
    Regex("<color=(#[0-9A-Fa-f]{6,8})>(.*?)</color>", RegexOption.DOT_MATCHES_ALL)

private fun parseText(
    text: String
): AnnotatedString
{
    return buildAnnotatedString {
        var last = 0

        COLOR_REGEX.findAll(text).forEach { match ->
            append(text.substring(last, match.range.first))

            val color = Color(
                ("FF" + match.groupValues[1].removePrefix("#")).toLong(16)
                    .toULong()
            )

            withStyle(SpanStyle(color = color)) {
                append(match.groupValues[2])
            }

            last = match.range.last + 1
        }

        append(text.substring(last))
    }
}