// UAT stage 2 assisted by Codex, 2026-11-24; human review pending.
package com.example.mylittlechef.ui.components

import androidx.annotation.DrawableRes
import androidx.compose.animation.Crossfade
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shape
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/** Shared visual only: the owning tile supplies click and selection semantics. */
@Composable
fun SelectionBadge(
    name: String, @DrawableRes resource: Int, background: Color,
    selected: Boolean = false, modifier: Modifier = Modifier,
    size: Dp = 36.dp, shape: Shape = CircleShape, iconTag: String? = null
) {
    val color by animateColorAsState(
        if (selected) lerp(background, Color.Black, .18f) else background,
        tween(140), label = "selection-background"
    )
    Box(modifier.size(size).clip(shape).background(color).semantics { contentDescription = name },
        contentAlignment = Alignment.Center) {
        Crossfade(selected, animationSpec = tween(130), label = "selection-check") { checked ->
            if (checked) Canvas(Modifier.size(size * .72f).testTag("selected-icon-$name")) {
                val ink = Color(0xFF172C25)
                drawLine(ink, Offset(this.size.width*.19f,this.size.height*.52f),
                    Offset(this.size.width*.43f,this.size.height*.75f), strokeWidth=this.size.width*.10f,cap=StrokeCap.Round)
                drawLine(ink, Offset(this.size.width*.43f,this.size.height*.75f),
                    Offset(this.size.width*.83f,this.size.height*.25f), strokeWidth=this.size.width*.10f,cap=StrokeCap.Round)
            } else Icon(painterResource(resource), null,
                Modifier.size(size * .82f).then(if(iconTag!=null) Modifier.testTag(iconTag) else Modifier),
                tint = Color(0xFF172C25))
        }
    }
}
