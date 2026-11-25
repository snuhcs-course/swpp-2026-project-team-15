// Scoped camera orientation assisted by Codex, 2026-11-25; human review pending.
package com.example.mylittlechef.ui.fridge.add

import android.content.pm.ActivityInfo
import android.view.OrientationEventListener
import androidx.activity.compose.LocalActivity
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.compose.runtime.*
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.example.mylittlechef.domain.captureRotationForDegrees

/** General screens stay portrait; only this route accepts sensor-driven landscape. */
@Composable
internal fun CameraOnlyRotation():()->Unit {
    val activity=LocalActivity.current
    val portrait=remember(activity) {{activity?.requestedOrientation=ActivityInfo.SCREEN_ORIENTATION_PORTRAIT;Unit}}
    DisposableEffect(activity) {
        activity?.requestedOrientation=ActivityInfo.SCREEN_ORIENTATION_SENSOR
        onDispose {
            if(activity!=null && !activity.isChangingConfigurations) portrait()
        }
    }
    return portrait
}

/** Sensor-driven output direction is independent of the control layout. */
@Composable
internal fun CaptureOutputOrientation(imageCapture:ImageCapture,analysis:ImageAnalysis) {
    val context=LocalContext.current
    val lifecycle=LocalLifecycleOwner.current.lifecycle
    DisposableEffect(context,lifecycle,imageCapture,analysis) {
        val sensor=object:OrientationEventListener(context) {
            override fun onOrientationChanged(orientation:Int) {
                val rotation=captureRotationForDegrees(orientation) ?: return
                if(imageCapture.targetRotation!=rotation) imageCapture.targetRotation=rotation
                if(analysis.targetRotation!=rotation) analysis.targetRotation=rotation
            }
        }
        fun update() {
            if(lifecycle.currentState.isAtLeast(Lifecycle.State.RESUMED) && sensor.canDetectOrientation()) sensor.enable()
            else sensor.disable()
        }
        val observer=LifecycleEventObserver {_,_->update()}
        lifecycle.addObserver(observer);update()
        onDispose {lifecycle.removeObserver(observer);sensor.disable()}
    }
}
