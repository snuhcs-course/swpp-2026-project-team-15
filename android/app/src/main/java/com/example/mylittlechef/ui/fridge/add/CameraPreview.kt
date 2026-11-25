// Preview rotation without rebinding assisted by Codex, 2026-11-25; human review pending.
// AI-generated initial CameraX preview scaffold with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
package com.example.mylittlechef.ui.fridge.add

import android.content.Context
import android.net.Uri
import android.util.Log
import android.view.View
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import java.io.File

private const val TAG = "CameraPreview"

@Composable
fun CameraPreview(
    imageCapture: ImageCapture,
    modifier: Modifier = Modifier,
    // When set (video mode) the preview is bound to this stream instead of to [imageCapture].
    imageAnalysis: ImageAnalysis? = null
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    val previewView = remember {
        PreviewView(context).apply {
            scaleType = PreviewView.ScaleType.FILL_CENTER
        }
    }

    val previewUseCase=remember(previewView) {
        Preview.Builder().build().also {it.setSurfaceProvider(previewView.surfaceProvider)}
    }

    DisposableEffect(lifecycleOwner, imageCapture, imageAnalysis) {
        val providerFuture = ProcessCameraProvider.getInstance(context)
        var provider: ProcessCameraProvider? = null
        var disposed=false
        val rotationListener=View.OnLayoutChangeListener {view,_,_,_,_,_,_,_,_ ->
            view.display?.rotation?.let {previewUseCase.targetRotation=it}
        }
        previewView.addOnLayoutChangeListener(rotationListener)

        providerFuture.addListener({
            if(disposed) return@addListener
            val cameraProvider = providerFuture.get()
            provider = cameraProvider

            previewView.display?.rotation?.let {previewUseCase.targetRotation=it}

            try {
                cameraProvider.unbindAll()
                cameraProvider.bindToLifecycle(
                    lifecycleOwner,
                    CameraSelector.DEFAULT_BACK_CAMERA,
                    previewUseCase,
                    imageAnalysis ?: imageCapture
                )
            } catch (e: Exception) {
                Log.e(TAG, "fail to connect camera", e)
            }
        }, ContextCompat.getMainExecutor(context))

        onDispose {
            disposed=true
            previewView.removeOnLayoutChangeListener(rotationListener)
            provider?.unbindAll()
        }
    }

    AndroidView(
        factory = { previewView },
        modifier = modifier
    )
}

fun takePhoto(
    context: Context,
    imageCapture: ImageCapture,
    onSaved: (Uri) -> Unit,
    onError: (ImageCaptureException) -> Unit
)
{
    val file = File(context.cacheDir, "capture_${System.currentTimeMillis()}.jpg")
    val outputOptions = ImageCapture.OutputFileOptions.Builder(file).build()

    imageCapture.takePicture(
        outputOptions,
        ContextCompat.getMainExecutor(context),
        object : ImageCapture.OnImageSavedCallback {
            override fun onImageSaved(output: ImageCapture.OutputFileResults) {
                onSaved(Uri.fromFile(file))
            }

            override fun onError(exception: ImageCaptureException) {
                Log.e(TAG, "fail to take a photo", exception)
                onError(exception)
            }
        }
    )
}
