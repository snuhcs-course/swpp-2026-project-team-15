// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
package com.mylittlechef.researchdemo

/** Result of one view-overlap estimate. [reliable] is false when the homography could not be trusted. */
data class Overlap(val value: Float, val reliable: Boolean)

/**
 * Selection rules: blur gate, overlap groups and farthest-first (an unknown overlap counts as 0.5).
 * Pure Kotlin so the logic does not depend on the camera or OpenCV.
 */
object Selector {
    const val GATE_RATIO = 0.5
    const val MIN_OVERLAP = 0.5f
    const val UNKNOWN_OVERLAP = 0.5f
    const val CAP = 8

    /** numpy.median semantics (mean of the two middle values for an even count). */
    fun median(values: DoubleArray): Double {
        if (values.isEmpty()) return 0.0
        val s = values.sortedArray()
        return if (s.size % 2 == 1) s[s.size / 2] else (s[s.size / 2 - 1] + s[s.size / 2]) / 2
    }

    /** Frames whose sharpness is at least [ratio] x the clip median pass (0.5, or 0.7 for the strict variant). */
    fun gate(sharpness: DoubleArray, ratio: Double = GATE_RATIO): BooleanArray {
        val limit = ratio * median(sharpness)
        return BooleanArray(sharpness.size) { sharpness[it] >= limit }
    }

    /**
     * Walk the kept frames in order. A frame joins the current group while its overlap with the group's first frame
     * (the anchor) is reliable and >= [MIN_OVERLAP]; an unreliable estimate or a lower overlap starts a new group.
     * [pair] (a, b) estimates the overlap of frame b seen from frame a.
     * Backstop: with [ts] (sensor timestamps, ns) a frame at least [maxGapNs] after the anchor also starts a new group.
     */
    fun group(
        kept: List<Int>, pair: (Int, Int) -> Overlap, onCompare: (Int, Overlap) -> Unit = { _, _ -> },
        ts: LongArray? = null, maxGapNs: Long = 0L,
    ): List<List<Int>> {
        if (kept.isEmpty()) return emptyList()
        val groups = mutableListOf(mutableListOf(kept[0]))
        var anchor = kept[0]
        for (i in kept.drop(1)) {
            val ov = pair(anchor, i)
            onCompare(i, ov)
            val effective = if (ov.reliable) ov.value else 0f
            val gap = ts != null && maxGapNs > 0 && ts[i] - ts[anchor] >= maxGapNs
            if (effective < MIN_OVERLAP || gap) {
                groups.add(mutableListOf(i))
                anchor = i
            } else {
                groups.last().add(i)
            }
        }
        return groups
    }

    /** Greedy farthest-first: repeatedly add the representative whose largest overlap with the chosen set is smallest.
     *  With [temporalTieBreak], exactly equal scores go to the candidate farthest in time from the chosen frames;
     *  without it the earliest candidate wins, which clusters the picks when many overlaps are unknown. */
    fun farthestFirst(reps: List<Int>, k: Int, pair: (Int, Int) -> Overlap, temporalTieBreak: Boolean = true): List<Int> {
        if (reps.size <= k) return reps.toList()
        fun known(o: Overlap) = if (o.reliable) o.value else UNKNOWN_OVERLAP
        val chosen = mutableListOf(reps[0])
        while (chosen.size < k) {
            var best = -1
            var bestScore = 2f
            var bestDist = -1
            for (r in reps) {
                if (r in chosen) continue
                val score = chosen.maxOf { c -> maxOf(known(pair(r, c)), known(pair(c, r))) }
                // Among exactly equal best scores take the candidate whose nearest chosen frame is farthest in frame
                // index; remaining ties keep the earliest candidate.
                val dist = if (temporalTieBreak) chosen.minOf { c -> Math.abs(r - c) } else 0
                if (score < bestScore || (temporalTieBreak && score == bestScore && dist > bestDist)) {
                    best = r
                    bestScore = score
                    bestDist = dist
                }
            }
            chosen.add(best)
        }
        return chosen.sorted()
    }
}
