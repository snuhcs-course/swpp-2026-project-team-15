// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
package com.mylittlechef.researchdemo

/** Grayscale image with row-major bytes. */
class Gray(val w: Int, val h: Int, val data: ByteArray)

object Metrics {
    /** Area-average downscale of a Y plane (pixelStride 1) so the long side equals [longSide]. */
    fun downscale(y: ByteArray, rowStride: Int, w: Int, h: Int, longSide: Int): Gray {
        val scale = longSide.toDouble() / maxOf(w, h)
        val ow = maxOf(1, Math.round(w * scale).toInt())
        val oh = maxOf(1, Math.round(h * scale).toInt())
        val out = ByteArray(ow * oh)
        for (oy in 0 until oh) {
            val y0 = oy * h / oh
            val y1 = maxOf(y0 + 1, (oy + 1) * h / oh)
            for (ox in 0 until ow) {
                val x0 = ox * w / ow
                val x1 = maxOf(x0 + 1, (ox + 1) * w / ow)
                var sum = 0
                for (yy in y0 until y1) {
                    val row = yy * rowStride
                    for (xx in x0 until x1) sum += y[row + xx].toInt() and 0xFF
                }
                out[oy * ow + ox] = (sum / ((y1 - y0) * (x1 - x0))).toByte()
            }
        }
        return Gray(ow, oh, out)
    }

    /** Variance of the 4-neighbour Laplacian over interior pixels (the border is skipped, unlike cv2.Laplacian). */
    fun laplacianVariance(g: Gray): Double {
        val w = g.w
        val d = g.data
        var sum = 0.0
        var sumSq = 0.0
        var n = 0
        for (yy in 1 until g.h - 1) {
            for (xx in 1 until w - 1) {
                val i = yy * w + xx
                val lap = (d[i - 1].toInt() and 0xFF) + (d[i + 1].toInt() and 0xFF) +
                    (d[i - w].toInt() and 0xFF) + (d[i + w].toInt() and 0xFF) - 4 * (d[i].toInt() and 0xFF)
                sum += lap
                sumSq += lap.toDouble() * lap
                n++
            }
        }
        if (n == 0) return 0.0
        val mean = sum / n
        return sumSq / n - mean * mean
    }

    fun meanBrightness(g: Gray): Double {
        var s = 0L
        for (b in g.data) s += b.toInt() and 0xFF
        return s.toDouble() / g.data.size
    }

    fun percentile(sorted: DoubleArray, p: Double): Double {
        if (sorted.isEmpty()) return Double.NaN
        val rank = Math.ceil(p / 100.0 * sorted.size).toInt().coerceIn(1, sorted.size)
        return sorted[rank - 1]
    }
}
