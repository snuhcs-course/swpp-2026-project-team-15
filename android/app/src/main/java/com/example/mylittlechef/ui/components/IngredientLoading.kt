// UAT stage 3 assisted by Codex, 2026-11-24; human review pending.
package com.example.mylittlechef.ui.components

import android.database.ContentObserver
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.*
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.*
import androidx.compose.ui.unit.dp
import androidx.compose.ui.text.style.TextAlign
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive

enum class LoadingTask(val message:String) {
    DISHES("만들 수 있는 요리를 찾고 있어요"),
    RECIPE("레시피를 불러오고 있어요"),
    REVISION("내 재료에 맞게 레시피를 바꾸고 있어요"),
    RECOGNITION("식재료를 찾고 있어요")
}

internal val LocalLoadingMotionOverride=staticCompositionLocalOf<Boolean?> {null}
internal fun loadingMotionAllowed(animator:Float,transition:Float)=animator>.5f && transition>.5f

/** Changes presentation only. The caller's request state controls its lifetime. */
@Composable
fun IngredientLoading(task:LoadingTask, modifier:Modifier=Modifier) {
    val resolver=LocalContext.current.contentResolver
    var motion by remember(resolver) {mutableStateOf(true)}
    DisposableEffect(resolver) {
        fun update() {
            motion=loadingMotionAllowed(Settings.Global.getFloat(resolver,Settings.Global.ANIMATOR_DURATION_SCALE,1f),
                Settings.Global.getFloat(resolver,Settings.Global.TRANSITION_ANIMATION_SCALE,1f))
        }
        val observer=object:ContentObserver(Handler(Looper.getMainLooper())) {
            override fun onChange(selfChange:Boolean) {update()}
        }
        update()
        listOf(Settings.Global.ANIMATOR_DURATION_SCALE,Settings.Global.TRANSITION_ANIMATION_SCALE).forEach {
            resolver.registerContentObserver(Settings.Global.getUriFor(it),false,observer)
        }
        onDispose {resolver.unregisterContentObserver(observer)}
    }
    val animate=LocalLoadingMotionOverride.current ?: motion
    val owner=LocalLifecycleOwner.current
    var index by remember {mutableIntStateOf(0)}
    LaunchedEffect(owner,animate) {
        if(!animate) {index=0;return@LaunchedEffect}
        owner.lifecycle.repeatOnLifecycle(Lifecycle.State.STARTED) {
            while(isActive) {delay(900);index=(index+1)%4}
        }
    }
    Box(modifier.fillMaxWidth().heightIn(min=128.dp).padding(vertical=12.dp)
        .semantics(mergeDescendants=true) {liveRegion=LiveRegionMode.Polite},
        contentAlignment=Alignment.Center) {
        Column(horizontalAlignment=Alignment.CenterHorizontally,
            verticalArrangement=Arrangement.spacedBy(12.dp)) {
        Crossfade(index,animationSpec=tween(if(animate) 180 else 0),label="loading-ingredient") { value ->
            IngredientBadge(listOf("계란","당근","두부","대파")[value],
                Modifier.clearAndSetSemantics {testTag="loading-icon-$value"},40.dp)
        }
        Text(task.message,Modifier.fillMaxWidth(),style=MaterialTheme.typography.bodyMedium,
            textAlign=TextAlign.Center,color=MaterialTheme.colorScheme.onSurface)
        }
    }
}
