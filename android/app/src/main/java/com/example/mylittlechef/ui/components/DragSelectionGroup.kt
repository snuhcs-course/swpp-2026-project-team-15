// UAT stage 2 assisted by Codex, 2026-11-24; human review pending.
package com.example.mylittlechef.ui.components

import androidx.compose.foundation.gestures.detectDragGesturesAfterLongPress
import androidx.compose.foundation.layout.Box
import androidx.compose.runtime.*
import kotlinx.coroutines.launch
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.*
import com.example.mylittlechef.domain.SelectionStroke

internal class SelectionTargets {
    val items = mutableMapOf<String, LayoutCoordinates>()
    var suppressClick = false
    var coordinates: LayoutCoordinates? = null
}
internal val LocalSelectionTargets = staticCompositionLocalOf<SelectionTargets?> { null }

/** Only this grid receives long-drag gestures; scrolling outside it and all action buttons remain independent. */
@Composable
fun DragSelectionGroup(
    selected: Set<String>, onSelectionChange: (Set<String>) -> Unit,
    modifier: Modifier = Modifier, enabled: Boolean = true,
    onStart: (String) -> Unit = {}, content: @Composable () -> Unit
) {
    val targets = remember { SelectionTargets() }
    val scope = rememberCoroutineScope()
    fun finishGesture() {
        // A mode change can recreate a child's clickable while its finger is still down.
        // Keep the release consumed as a long gesture until that event has finished dispatching.
        scope.launch { withFrameNanos { }; targets.suppressClick = false }
    }
    val currentSelected by rememberUpdatedState(selected)
    val setSelected by rememberUpdatedState(onSelectionChange)
    val start by rememberUpdatedState(onStart)
    Box(modifier.onGloballyPositioned { targets.coordinates = it }.pointerInput(enabled) {
        if (!enabled) return@pointerInput
        var stroke: SelectionStroke? = null
        var previous = Offset.Zero
        var workingSelection = linkedSetOf<String>()
        fun rects(): List<Pair<String,Rect>> = targets.items.mapNotNull { (key, coordinates) ->
            if(coordinates.isAttached) key to coordinates.boundsInRoot() else null
        }
        fun apply(name: String) {
            stroke?.let {
                if(it.visit(name)) {
                    if(it.selecting) workingSelection.add(name) else workingSelection.remove(name)
                    setSelected(workingSelection.toSet())
                }
            }
        }
        detectDragGesturesAfterLongPress(
            onDragStart = { local ->
                val root = targets.coordinates?.takeIf {it.isAttached}?.localToRoot(local)
                val first = root?.let { point -> rects().firstOrNull { it.second.contains(point) }?.first }
                if(first!=null) {
                    targets.suppressClick = true
                    workingSelection = LinkedHashSet(currentSelected)
                    stroke = SelectionStroke(first !in currentSelected)
                    previous = root
                    start(first)
                    apply(first)
                }
            },
            onDrag = { change, _ ->
                if(stroke!=null) {
                    val next=targets.coordinates?.takeIf {it.isAttached}?.localToRoot(change.position)
                    if(next!=null) {
                        rects().filter { segmentHits(it.second,previous,next) }.forEach { apply(it.first) }
                        previous=next
                    }
                    change.consume()
                }
            },
            onDragEnd = { stroke=null; finishGesture() }, onDragCancel = { stroke=null; finishGesture() }
        )
    }) { CompositionLocalProvider(LocalSelectionTargets provides targets, content=content) }
}

/** Coordinates are read at hit time so scroll/reflow never leaves stale rectangles. */
fun Modifier.selectionTarget(name: String): Modifier = composed {
    val targets=LocalSelectionTargets.current
    DisposableEffect(targets,name) { onDispose { targets?.items?.remove(name) } }
    this.onGloballyPositioned { if(targets!=null) targets.items[name]=it }
}

private fun segmentHits(rect: Rect, from: Offset, to: Offset): Boolean {
    if(rect.width<=0f || rect.height<=0f) return false
    var low=0f;var high=1f
    val delta=to-from
    fun clip(p: Float,q: Float): Boolean {
        if(p==0f) return q>=0f
        val t=q/p
        if(p<0f) low=maxOf(low,t) else high=minOf(high,t)
        return low<=high
    }
    return clip(-delta.x,from.x-rect.left) && clip(delta.x,rect.right-from.x) &&
        clip(-delta.y,from.y-rect.top) && clip(delta.y,rect.bottom-from.y)
}
