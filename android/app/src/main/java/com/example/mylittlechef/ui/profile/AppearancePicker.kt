// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui.profile

import androidx.compose.foundation.layout.Box
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import com.example.mylittlechef.domain.ThemeMode
import com.example.mylittlechef.ui.theme.LocalAppearanceSettings

@Composable
fun AppearancePicker() {
    val appearance=LocalAppearanceSettings.current
    var expanded by remember { mutableStateOf(false) }
    Box {
        IconButton(onClick={ expanded=true },enabled=!appearance.saving,
            modifier=Modifier.semantics { contentDescription="화면 모드 설정: ${appearance.mode.label}" }) {
            Text(if(appearance.mode==ThemeMode.DARK) "☾" else "☀",style=MaterialTheme.typography.headlineSmall,
                color=MaterialTheme.colorScheme.primary)
        }
        DropdownMenu(expanded=expanded,onDismissRequest={expanded=false}) {
            ThemeMode.entries.forEach { option ->
                DropdownMenuItem(text={Text(option.label)},onClick={expanded=false; appearance.onSelect(option)},
                    trailingIcon={if(option==appearance.mode) Text("✓")})
            }
        }
    }
}
