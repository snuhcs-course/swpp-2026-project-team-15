// UI ergonomics and theme changes assisted by Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui.theme

import android.app.Activity
import android.os.Build
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.dynamicDarkColorScheme
import androidx.compose.material3.dynamicLightColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.graphics.Color
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat

private val DarkColorScheme = darkColorScheme(
    primary = Color(0xFFA5D89A), onPrimary = Color(0xFF12320F), tertiary=Color(0xFFD7B9EA),
    primaryContainer = Color(0xFF284A24), onPrimaryContainer = Color(0xFFD0EDC7),
    secondary = Color(0xFFB7CEAC), onSecondary = Color(0xFF253420),
    background = Color(0xFF121710), onBackground = Color(0xFFE3E9DE),
    surface = Color(0xFF121710), onSurface = Color(0xFFE3E9DE),
    surfaceVariant = Color(0xFF283025), onSurfaceVariant = Color(0xFFC1CAB9),
    outline = Color(0xFF899580), outlineVariant = Color(0xFF424D3D),
    errorContainer = Color(0xFF5B2B25), onErrorContainer = Color(0xFFFFDAD4)
)

private val LightColorScheme = lightColorScheme(
    primary = Color(0xFF105E0F), onPrimary = Color.White, tertiary=Color(0xFF70528C),
    primaryContainer = Color(0xFFD8EED1), onPrimaryContainer = Color(0xFF163412),
    secondary = Color(0xFF52634A), onSecondary = Color.White,
    background = Color(0xFFFCFDF8), onBackground = Color(0xFF192017),
    surface = Color(0xFFFCFDF8), onSurface = Color(0xFF192017),
    surfaceVariant = Color(0xFFF0F2EB), onSurfaceVariant = Color(0xFF485342),
    outline = Color(0xFF737F6B), outlineVariant = Color(0xFFC5CDBD),
    errorContainer = Color(0xFFF9E7E2), onErrorContainer = Color(0xFF8A3D32)

    /* Other default colors to override
    background = Color(0xFFFFFBFE),
    surface = Color(0xFFFFFBFE),
    onPrimary = Color.White,
    onSecondary = Color.White,
    onTertiary = Color.White,
    onBackground = Color(0xFF1C1B1F),
    onSurface = Color(0xFF1C1B1F),
    */
)

@Composable
fun MyLittleChefTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    // Dynamic color is available on Android 12+
    dynamicColor: Boolean = false,
    content: @Composable () -> Unit
) {
    val colorScheme = when {
        dynamicColor && Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> {
            val context = LocalContext.current
            if (darkTheme) dynamicDarkColorScheme(context) else dynamicLightColorScheme(context)
        }

        darkTheme -> DarkColorScheme
        else -> LightColorScheme
    }

    val view=LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            (view.context as? Activity)?.window?.let { window ->
                WindowCompat.getInsetsController(window,view).apply {
                    isAppearanceLightStatusBars=!darkTheme
                    isAppearanceLightNavigationBars=!darkTheme
                }
            }
        }
    }
    MaterialTheme(
        colorScheme = colorScheme,
        typography = Typography,
        content = content
    )
}
