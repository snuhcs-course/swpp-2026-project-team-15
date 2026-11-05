// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import com.example.mylittlechef.data.local.PreferencesThemeRepository
import com.example.mylittlechef.data.local.localDataStore
import com.example.mylittlechef.domain.ThemeMode
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

data class AppearanceSettings(
    val mode: ThemeMode=ThemeMode.SYSTEM,
    val saving: Boolean=false,
    val error: String?=null,
    val onSelect: (ThemeMode)->Unit={}
)

val LocalAppearanceSettings=staticCompositionLocalOf { AppearanceSettings() }

@Composable
fun AppearanceSettingsHost(content: @Composable ()->Unit) {
    val context=LocalContext.current.applicationContext
    val repository=remember(context) { PreferencesThemeRepository(context.localDataStore) }
    val loadedMode by produceState<ThemeMode?>(null,repository) { repository.mode.collect { value=it } }
    val mode=loadedMode ?: return
    val scope=rememberCoroutineScope()
    var saving by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val settings=AppearanceSettings(mode,saving,error) { requested ->
        if (!saving) {
            saving=true; error=null
            scope.launch {
                try { repository.set(requested) }
                catch (cancelled:CancellationException) { throw cancelled }
                catch (_:Exception) { error="화면 설정을 저장하지 못했어요. 다시 선택해 주세요." }
                finally { saving=false }
            }
        }
    }
    CompositionLocalProvider(LocalAppearanceSettings provides settings) {
        MyLittleChefTheme(darkTheme=mode.isDark(isSystemInDarkTheme())) {
            Surface(Modifier.fillMaxSize()) { content() }
        }
    }
}
