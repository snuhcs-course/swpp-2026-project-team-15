// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
package com.example.mylittlechef.data.sweep

import android.content.Context
import android.graphics.Bitmap
import android.graphics.Matrix
import android.net.Uri
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.util.Size
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageProxy
import androidx.camera.core.resolutionselector.AspectRatioStrategy
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import com.example.mylittlechef.domain.sweep.FrameSharpness
import com.example.mylittlechef.domain.sweep.SweepFiles
import com.example.mylittlechef.domain.sweep.SweepSelector
import java.io.File
import java.util.concurrent.Executors
import kotlin.math.max

private const val TAG = "SweepRecorder"

/**
 * Records a few seconds of the camera stream and keeps the sharpest frame of each time bin
 * (see [SweepSelector]). Frames are resized to [UPLOAD_SIDE] px on the long side and written as
 * JPEG without metadata into a `sweep-<millis>` cache folder ([SweepFiles]).
 *
 * Bind [analysis] next to the camera preview, then call [start]. All frame work runs on one
 * background thread; at most [SweepSelector.DEFAULT_BINS] resized frames are held at a time.
 */
class SweepRecorder(
    private val context: Context,
    private val durationMs: Long = DURATION_MS
) {
    val analysis: ImageAnalysis = ImageAnalysis.Builder()
        .setResolutionSelector(
            ResolutionSelector.Builder()
                .setAspectRatioStrategy(AspectRatioStrategy.RATIO_16_9_FALLBACK_AUTO_STRATEGY)
                .setResolutionStrategy(
                    ResolutionStrategy(
                        Size(1280, 720),
                        ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER
                    )
                )
                .build()
        )
        .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
        .build()

    private val executor = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())

    // Touched only on [executor].
    private var selector: SweepSelector? = null
    private val held = HashMap<Int, Bitmap>()
    private var firstTimestampNs = -1L
    private var frameCount = 0
    private var finishing = false
    private var onDone: ((Uri?) -> Unit)? = null
    private var onProgress: ((Float) -> Unit)? = null

    /**
     * Start a sweep. [onProgress] gets 0..1 while recording and [onDone] the preview frame URI,
     * or null when no usable frame arrived. Both run on the main thread.
     */
    fun start(onProgress: (Float) -> Unit, onDone: (Uri?) -> Unit) {
        executor.execute {
            SweepFiles.deleteStale(context.cacheDir, System.currentTimeMillis(), STALE_AFTER_MS)
            selector = SweepSelector(durationMs * 1_000_000L)
            held.values.forEach { it.recycle() }
            held.clear()
            firstTimestampNs = -1L
            frameCount = 0
            finishing = false
            this.onDone = onDone
            this.onProgress = onProgress
            analysis.setAnalyzer(executor) { frame -> frame.use { handle(it) } }
            // Frames normally end the sweep; this covers a stream that stalls.
            main.postDelayed({ executor.execute { finish() } }, durationMs + STALL_GRACE_MS)
        }
    }

    /** Stop without producing files, e.g. when the screen is left. */
    fun cancel() {
        executor.execute {
            finishing = true
            analysis.clearAnalyzer()
            held.values.forEach { it.recycle() }
            held.clear()
            onDone = null
            onProgress = null
        }
    }

    private fun handle(frame: ImageProxy) {
        val active = selector
        if (finishing || active == null) return
        if (firstTimestampNs < 0) firstTimestampNs = frame.imageInfo.timestamp
        val elapsedNs = frame.imageInfo.timestamp - firstTimestampNs
        val plane = frame.planes[0]
        val gray = FrameSharpness.sampleLuma(
            plane.buffer, plane.rowStride, plane.pixelStride, frame.width, frame.height
        )
        val sharpness = FrameSharpness.laplacianVariance(gray)
        val index = frameCount++
        val offer = active.offer(elapsedNs, sharpness)
        if (offer.keep) {
            val bitmap = upright(frame)
            if (bitmap != null) held[index] = bitmap
            offer.release?.let { held.remove(it)?.recycle() }
        }
        val fraction = (elapsedNs.toFloat() / (durationMs * 1_000_000L)).coerceIn(0f, 1f)
        onProgress?.let { callback -> main.post { callback(fraction) } }
        if (elapsedNs >= durationMs * 1_000_000L) finish()
    }

    private fun finish() {
        if (finishing) return
        finishing = true
        analysis.clearAnalyzer()
        val done = onDone
        val uri = runCatching { write() }.onFailure { Log.e(TAG, "sweep failed", it) }.getOrNull()
        held.values.forEach { it.recycle() }
        held.clear()
        onDone = null
        onProgress = null
        main.post { done?.invoke(uri) }
    }

    private fun write(): Uri? {
        val result = selector?.finish() ?: return null
        val usable = result.indices.filter { it in held }
        if (usable.isEmpty()) return null
        val preview = if (result.representative in held) result.representative else usable.first()
        val order = listOf(preview) + usable.filter { it != preview }
        val dir = File(context.cacheDir, SweepFiles.directoryName(System.currentTimeMillis()))
        check(dir.mkdirs()) { "cannot create ${dir.name}" }
        order.forEachIndexed { position, index ->
            File(dir, SweepFiles.frameName(position)).outputStream().use {
                held.getValue(index).compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, it)
            }
        }
        Log.i(TAG, "sweep: ${frameCount} frames seen, ${order.size} kept, fallback=${result.singleFrameFallback}")
        return Uri.fromFile(File(dir, SweepFiles.frameName(0)))
    }

    /** Upright copy with the long side at most [UPLOAD_SIDE]; null if the frame cannot be read. */
    private fun upright(frame: ImageProxy): Bitmap? = runCatching {
        val source = frame.toBitmap()
        val scale = minOf(1f, UPLOAD_SIDE.toFloat() / max(source.width, source.height))
        val matrix = Matrix().apply {
            postScale(scale, scale)
            postRotate(frame.imageInfo.rotationDegrees.toFloat())
        }
        Bitmap.createBitmap(source, 0, 0, source.width, source.height, matrix, true).also {
            if (it !== source) source.recycle()
        }
    }.onFailure { Log.w(TAG, "frame conversion failed", it) }.getOrNull()

    companion object {
        /** Recommended sweep length: long enough to cross a fridge, short enough to hold steady. */
        const val DURATION_MS = 5_000L
        /** Same long side and quality as the measured upload settings. */
        const val UPLOAD_SIDE = 1024
        const val JPEG_QUALITY = 85
        private const val STALL_GRACE_MS = 2_000L
        private const val STALE_AFTER_MS = 10 * 60 * 1000L
    }
}
