// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
package com.mylittlechef.researchdemo

/**
 * Streaming version of the OVERLAP strategy (blur gate + view-overlap groups + sharpest per group + farthest-first with the temporal
 * tie-break) for the live camera: frames are pushed one by one, and only the frames that can still matter keep their
 * features (and, in the caller, their saved pixels).
 *
 * Retained at any time: the current group's anchor (its first frame), the sharpest frame of the current group, and the
 * sharpest frame of every closed group (the representatives). The number of representatives is capped at [maxReps]; beyond
 * that, the two neighbouring representatives that overlap most are merged by dropping the less sharp one. Everything
 * else is released as soon as it is clear that it cannot be chosen.
 *
 * Difference from the offline OVERLAP (the only one): the blur gate cannot know the final clip median, so it uses the median of
 * the sharpness values seen so far (this frame included). When the two gates give the same decision for every frame, the
 * chosen frames are identical (unit-tested); how often they differ on real clips is measured, not assumed.
 *
 * [pair] (a, b) is the overlap of frame b seen from frame a and must work for every frame that was pushed and not yet
 * released. [release] is called once per frame when the caller can free its features and pixels. Pure Kotlin.
 */
class LiveSelector(
    cap: Int,
    private val ratio: Double = Selector.GATE_RATIO,
    private val maxGapNs: Long = ArmSelector.MAX_GAP_NS,
    private val maxReps: Int = DEFAULT_MAX_REPS,
    private val pair: (Int, Int) -> Overlap,
    private val release: (Int) -> Unit = {},
) {
    private val k = ArmSelector.clampCap(cap)
    private val seen = ArrayList<Double>() // sorted sharpness values seen so far (scalars only)
    private val sharp = HashMap<Int, Double>()
    private val ts = HashMap<Int, Long>()
    private val reps = ArrayList<Int>() // sharpest frame of each closed group, in time order
    private var anchor = -1
    private var best = -1
    private val adjacent = HashMap<Long, Float>()

    var pushed = 0; private set
    var gateRejected = 0; private set
    var groupsClosed = 0; private set
    var merges = 0; private set
    /** Most frames that were retained (features and pixels held) at the same time. */
    var maxRetained = 0; private set
    private val retained = HashSet<Int>()
    /** Gate decision per pushed frame, for replaying the run on the host. */
    val gateLog = ArrayList<Boolean>()

    /** Push frame [idx] (the caller already holds its features). Returns whether it passed the blur gate. */
    fun push(idx: Int, tsNs: Long, sharpness: Double): Boolean {
        pushed++
        retained.add(idx)
        sharp[idx] = sharpness; ts[idx] = tsNs
        insertSorted(sharpness)
        val pass = sharpness >= ratio * medianSoFar()
        gateLog.add(pass)
        if (!pass) {
            gateRejected++
            drop(idx)
        } else if (anchor < 0) {
            anchor = idx; best = idx
        } else {
            val ov = pair(anchor, idx)
            val effective = if (ov.reliable) ov.value else 0f
            val gap = maxGapNs > 0 && tsNs - ts.getValue(anchor) >= maxGapNs
            if (effective < Selector.MIN_OVERLAP || gap) {
                closeGroup()
                anchor = idx; best = idx
            } else {
                if (sharpness > sharp.getValue(best)) {
                    val old = best
                    best = idx
                    if (old != anchor) drop(old)
                } else if (idx != anchor) {
                    drop(idx)
                }
            }
        }
        maxRetained = maxOf(maxRetained, retained.size)
        return pass
    }

    /** The chosen frames (indices as pushed), sorted. Releases everything still held. */
    fun finish(): List<Int> {
        if (anchor >= 0) closeGroup()
        val chosen = Selector.farthestFirst(reps.toList(), k, pair, temporalTieBreak = true)
        val keep = chosen.toSet()
        for (r in reps.toList()) if (r !in keep) drop(r)
        return chosen
    }

    fun isHeld(idx: Int) = idx in retained

    /** Frames whose features/pixels are still held (valid after [finish]: the chosen ones). */
    fun heldFrames(): Set<Int> = retained.toSet()

    private fun closeGroup() {
        groupsClosed++
        if (anchor != best) drop(anchor) // the best stays; the anchor is no longer needed
        reps.add(best)
        anchor = -1; best = -1
        while (reps.size > maxReps) mergeClosestNeighbours()
    }

    private fun mergeClosestNeighbours() {
        var at = 0
        var most = -1f
        for (i in 0 until reps.size - 1) {
            val key = reps[i].toLong() * 1_000_000 + reps[i + 1]
            val ov = adjacent.getOrPut(key) { val o = pair(reps[i], reps[i + 1]); if (o.reliable) o.value else Selector.UNKNOWN_OVERLAP }
            if (ov > most) { most = ov; at = i }
        }
        val a = reps[at]; val b = reps[at + 1]
        val dropIdx = if (sharp.getValue(a) >= sharp.getValue(b)) b else a
        reps.remove(dropIdx)
        drop(dropIdx)
        merges++
    }

    private fun drop(idx: Int) {
        if (retained.remove(idx)) release(idx)
    }

    private fun insertSorted(v: Double) {
        var lo = 0; var hi = seen.size
        while (lo < hi) { val mid = (lo + hi) ushr 1; if (seen[mid] < v) lo = mid + 1 else hi = mid }
        seen.add(lo, v)
    }

    /** numpy.median semantics over the values seen so far. */
    private fun medianSoFar(): Double {
        val n = seen.size
        return if (n % 2 == 1) seen[n / 2] else (seen[n / 2 - 1] + seen[n / 2]) / 2
    }

    companion object {
        const val DEFAULT_MAX_REPS = 60
    }
}
