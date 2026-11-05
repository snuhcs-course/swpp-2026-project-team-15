// UI ergonomics and theme changes assisted by Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui.theme

import androidx.compose.ui.graphics.Color
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable

val Purple80 = Color(0xFFD0BCFF)
val PurpleGrey80 = Color(0xFFCCC2DC)
val Pink80 = Color(0xFFEFB8C8)

val Purple40 = Color(0xFF6650a4)
val PurpleGrey40 = Color(0xFF625b71)
val Pink40 = Color(0xFF7D5260)

val GreenGray: Color
    @Composable get() = MaterialTheme.colorScheme.outline
val DeepGreen: Color
    @Composable get() = MaterialTheme.colorScheme.primary

val Gray: Color
    @Composable get() = MaterialTheme.colorScheme.surfaceVariant

val DeepBrown: Color
    @Composable get() = MaterialTheme.colorScheme.primary
