// Cold-launch-only motion assisted by Codex, 2026-11-19; human review pending.
package com.example.mylittlechef.ui.components
import android.provider.Settings
import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.tween
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.R
import kotlinx.coroutines.delay
@Composable
fun StartupIntro(coldLaunch: Boolean, content: @Composable ()->Unit) {
    var visible by rememberSaveable { mutableStateOf(coldLaunch) }
    val context=LocalContext.current
    val progress=remember { Animatable(0f) }
    LaunchedEffect(Unit) {
        val scale=Settings.Global.getFloat(context.contentResolver,Settings.Global.ANIMATOR_DURATION_SCALE,1f)
        if(visible && coldLaunch && scale>0f) { progress.animateTo(1f,tween(450));delay(100);progress.animateTo(0f,tween(150)) }
        visible=false
    }
    Box(Modifier.fillMaxSize()) {
        content()
        if(visible && coldLaunch) Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)
            .testTag("startup-intro").clickable(indication=null,interactionSource=remember {MutableInteractionSource()}) {},contentAlignment=Alignment.Center) {
            Image(painterResource(R.drawable.ic_launcher_artwork),"My Little Chef",
                Modifier.size(104.dp).graphicsLayer { alpha=progress.value;scaleX=.92f+.08f*progress.value;scaleY=scaleX;translationY=8*(1-progress.value) }
                    .clip(RoundedCornerShape(28.dp)))
        }
    }
}
