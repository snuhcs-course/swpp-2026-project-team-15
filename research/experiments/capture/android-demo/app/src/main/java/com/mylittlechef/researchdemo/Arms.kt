// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
package com.mylittlechef.researchdemo

/**
 * Frame-selection strategies compared on one recorded clip, so every strategy sees the same frames. Pure Kotlin (no
 * Android or OpenCV types) so it runs in JVM unit tests.
 *
 * - SINGLE: the sharpest single analysis frame of the clip (a stand-in for a still photo, which this demo does not capture).
 * - UNIFORM: evenly spaced frame indices.
 * - TIME_BINS: the sharpest frame in each of k equal time bins.
 * - OVERLAP: blur gate (0.5 x median sharpness), groups of frames that share most of their view, the sharpest frame per
 *   group, then farthest-first by view overlap. Ties go to the candidate farthest in time from the chosen frames.
 * - OVERLAP_STRICT: the same with a blur gate of 0.7 x median.
 * - ALL: one frame about every 0.4 s.
 */
enum class Arm(val label: String) {
    SINGLE("single"), UNIFORM("uniform"), TIME_BINS("time-bins"), OVERLAP("overlap"),
    OVERLAP_STRICT("overlap-strict"), ALL("all");

    companion object {
        fun parse(text: String?): Arm? = entries.firstOrNull { it.label.equals(text, true) || it.name.equals(text, true) }
    }
}

data class ArmResult(
    val arm: Arm,
    val chosen: List<Int>,
    /** Frames that passed the blur gate and the groups, for the overlap strategies only. */
    val kept: List<Int>? = null,
    val groups: List<List<Int>>? = null,
)

object ArmSelector {
    const val MIN_CAP = 8
    const val MAX_CAP = 15
    const val STRICT_GATE_RATIO = 0.7
    /** ALL: one frame about every 0.4 s (2.5 per second). */
    const val ALL_INTERVAL_NS = 400_000_000L
    /** Backstop only: a group never spans more than this. */
    const val MAX_GAP_NS = 250_000_000L

    fun clampCap(k: Int) = k.coerceIn(MIN_CAP, MAX_CAP)

    /** numpy.linspace(0, n - 1, k).round(): step multiplication, last point exact, half-to-even rounding. */
    fun uniformIndices(n: Int, k: Int): List<Int> {
        if (n <= k) return (0 until n).toList()
        val step = (n - 1).toDouble() / (k - 1)
        return List(k) { i -> if (i == k - 1) n - 1 else Math.rint(i * step).toInt() }
    }

    /** Time (index) bins as numpy.linspace(0, n, k + 1).astype(int); the first sharpest frame of each non-empty bin. */
    fun timeBinIndices(sharp: DoubleArray, k: Int): List<Int> {
        val n = sharp.size
        val step = n.toDouble() / k
        val edges = IntArray(k + 1) { i -> if (i == k) n else (i * step).toInt() }
        val out = ArrayList<Int>()
        for (b in 0 until k) {
            val lo = edges[b]
            val hi = edges[b + 1]
            if (hi <= lo) continue
            var best = lo
            for (i in lo until hi) if (sharp[i] > sharp[best]) best = i
            out.add(best)
        }
        return out
    }

    fun denseIndices(ts: LongArray): List<Int> {
        if (ts.isEmpty()) return emptyList()
        val out = ArrayList<Int>()
        var next = 0L
        for (i in ts.indices) {
            if (ts[i] - ts[0] >= next) {
                out.add(i)
                next = ((ts[i] - ts[0]) / ALL_INTERVAL_NS + 1) * ALL_INTERVAL_NS
            }
        }
        return out
    }

    fun select(
        arm: Arm, sharp: DoubleArray, ts: LongArray, cap: Int,
        pair: (Int, Int) -> Overlap, onCompare: (Int, Overlap) -> Unit = { _, _ -> },
    ): ArmResult {
        val k = clampCap(cap)
        if (sharp.isEmpty()) return ArmResult(arm, emptyList())
        return when (arm) {
            Arm.SINGLE -> ArmResult(arm, listOf(sharp.indices.maxByOrNull { sharp[it] }!!))
            Arm.UNIFORM -> ArmResult(arm, uniformIndices(sharp.size, k))
            Arm.TIME_BINS -> ArmResult(arm, timeBinIndices(sharp, k))
            Arm.ALL -> ArmResult(arm, denseIndices(ts))
            Arm.OVERLAP, Arm.OVERLAP_STRICT -> {
                val ratio = if (arm == Arm.OVERLAP) Selector.GATE_RATIO else STRICT_GATE_RATIO
                val gate = Selector.gate(sharp, ratio)
                val kept = sharp.indices.filter { gate[it] }
                val groups = Selector.group(kept, pair, onCompare, ts, MAX_GAP_NS)
                val reps = groups.map { g -> g.maxByOrNull { sharp[it] }!! }
                ArmResult(arm, Selector.farthestFirst(reps, k, pair), kept, groups)
            }
        }
    }
}
