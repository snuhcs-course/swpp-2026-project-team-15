// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
package com.example.mylittlechef.domain.sweep

/**
 * Chooses which frames of a short fridge sweep to upload, one pass over the camera stream.
 *
 * The sweep is cut into [binCount] equal time bins and the sharpest frame of each bin is kept,
 * so the chosen frames cover the whole sweep and each one is as sharp as its neighbourhood allows.
 * Frames whose sharpness is below [gateRatio] times the median sharpness of the sweep are
 * dropped as blurred. At most [binCount] frames are ever held, which bounds memory.
 *
 * Why not group frames by visual overlap: on real fridge footage the overlap estimate failed for
 * 62% of frame pairs (ORB features + RANSAC), and sharpest-frame-only without time spreading
 * covered the sweep worst. Spreading in time plus a blur gate needs no feature matching.
 *
 * Usage: call [offer] for every frame; it tells the caller to keep the frame (and which earlier
 * frame to release). [finish] returns the frame indices to upload.
 */
class SweepSelector(
    private val durationNs: Long,
    val binCount: Int = DEFAULT_BINS,
    private val gateRatio: Double = GATE_RATIO
) {
    init {
        require(durationNs > 0) { "duration must be positive" }
        require(binCount in 1..MAX_FRAMES) { "binCount must be within 1..$MAX_FRAMES" }
        require(gateRatio >= 0.0) { "gateRatio must not be negative" }
    }

    /** What the caller must do with the frame it just offered. */
    class Offer(val keep: Boolean, val release: Int?)

    class Result(
        /** Indices to upload, in time order. */
        val indices: List<Int>,
        /** The sharpest chosen frame; it is shown as the preview. */
        val representative: Int,
        /** True when too few frames survived and only the sharpest one is returned. */
        val singleFrameFallback: Boolean
    )

    private val binBest = arrayOfNulls<Int>(binCount)
    private val sharpness = HashMap<Int, Double>()
    private val seen = ArrayList<Double>()
    private var next = 0

    /** Offer the next frame; [timestampNs] is relative to the start of the sweep. */
    fun offer(timestampNs: Long, frameSharpness: Double): Offer {
        val index = next++
        seen.add(frameSharpness)
        val bin = binOf(timestampNs)
        val current = binBest[bin]
        if (current != null && sharpness.getValue(current) >= frameSharpness) {
            return Offer(keep = false, release = null)
        }
        binBest[bin] = index
        sharpness[index] = frameSharpness
        if (current != null) sharpness.remove(current)
        return Offer(keep = true, release = current)
    }

    /** Indices of frames currently held, i.e. the best of each non-empty bin. */
    fun held(): List<Int> = binBest.filterNotNull().sorted()

    /** Apply the blur gate with the sweep's final median. Null when no frame was offered. */
    fun finish(): Result? {
        val held = held()
        if (held.isEmpty()) return null
        val sharpest = held.maxByOrNull { sharpness.getValue(it) }!!
        val limit = gateRatio * median()
        val passing = held.filter { sharpness.getValue(it) >= limit }
        if (passing.size < MIN_FRAMES) return Result(listOf(sharpest), sharpest, true)
        val representative = passing.maxByOrNull { sharpness.getValue(it) }!!
        return Result(passing, representative, false)
    }

    private fun binOf(timestampNs: Long): Int {
        val clamped = timestampNs.coerceIn(0L, durationNs - 1)
        return (clamped * binCount / durationNs).toInt().coerceIn(0, binCount - 1)
    }

    private fun median(): Double {
        val sorted = seen.sorted()
        val n = sorted.size
        return if (n % 2 == 1) sorted[n / 2] else (sorted[n / 2 - 1] + sorted[n / 2]) / 2
    }

    companion object {
        /** Upper bound of frames per request; the server accepts the same number. */
        const val MAX_FRAMES = 15
        const val DEFAULT_BINS = 10
        const val MIN_FRAMES = 2
        /** Same blur gate as the measured selection rules: below half the median is blurred. */
        const val GATE_RATIO = 0.5
    }
}
