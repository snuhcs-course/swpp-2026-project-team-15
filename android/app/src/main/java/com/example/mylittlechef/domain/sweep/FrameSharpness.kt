// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
package com.example.mylittlechef.domain.sweep

import java.nio.ByteBuffer

/** Grayscale samples, row-major, values 0..255. */
class GrayImage(val width: Int, val height: Int, val pixels: IntArray) {
    init {
        require(pixels.size == width * height) { "pixel count must be width * height" }
    }
}

/**
 * Cheap blur measure used to drop shaky frames while sweeping the fridge.
 *
 * The score is the variance of the 4-neighbour Laplacian on a copy whose long side is
 * [SAMPLE_SIDE] px. A sharp frame has strong local contrast changes and a high score; a blurred
 * frame of the same scene scores lower, so scores are only compared between frames of one sweep.
 */
object FrameSharpness {
    const val SAMPLE_SIDE = 256

    /**
     * Nearest-neighbour downsample of an 8-bit luma plane (the Y plane of a YUV frame).
     * [rowStride] and [pixelStride] come from the plane, so padded rows are handled.
     */
    fun sampleLuma(
        luma: ByteBuffer,
        rowStride: Int,
        pixelStride: Int,
        width: Int,
        height: Int,
        side: Int = SAMPLE_SIDE
    ): GrayImage {
        require(width > 0 && height > 0 && rowStride >= width * pixelStride)
        val step = maxOf(1, maxOf(width, height) / side)
        val w = (width + step - 1) / step
        val h = (height + step - 1) / step
        val out = IntArray(w * h)
        for (y in 0 until h) {
            val rowStart = y * step * rowStride
            for (x in 0 until w) {
                out[y * w + x] = luma.get(rowStart + x * step * pixelStride).toInt() and 0xFF
            }
        }
        return GrayImage(w, h, out)
    }

    /** Variance of the 4-neighbour Laplacian over the interior pixels; 0 for flat or tiny images. */
    fun laplacianVariance(image: GrayImage): Double {
        val w = image.width
        val h = image.height
        if (w < 3 || h < 3) return 0.0
        val p = image.pixels
        var sum = 0.0
        var sumSquares = 0.0
        var count = 0
        for (y in 1 until h - 1) {
            for (x in 1 until w - 1) {
                val i = y * w + x
                val laplacian = (p[i - 1] + p[i + 1] + p[i - w] + p[i + w] - 4 * p[i]).toDouble()
                sum += laplacian
                sumSquares += laplacian * laplacian
                count++
            }
        }
        val mean = sum / count
        return sumSquares / count - mean * mean
    }
}
