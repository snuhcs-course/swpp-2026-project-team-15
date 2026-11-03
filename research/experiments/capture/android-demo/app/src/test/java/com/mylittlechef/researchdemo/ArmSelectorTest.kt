// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
package com.mylittlechef.researchdemo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.abs

/**
 * Known-answer checks of the selection strategies on a 1-D sweep: frame i shows the window [x_i, x_i + W) of a long scene, so the
 * true overlap of two frames is 1 - |x_a - x_b| / W and the covered share of the scene is exact.
 */
class ArmSelectorTest {
    private val n = 120
    private val w = 400.0
    private val scene = 1600.0
    private val x = DoubleArray(n) { it * (scene - w) / (n - 1) }
    private val ts = LongArray(n) { it * 16_666_667L }
    private val sharp = DoubleArray(n) { 100.0 }
    private val exact = { a: Int, b: Int -> Overlap(maxOf(0.0, 1 - abs(x[a] - x[b]) / w).toFloat(), true) }

    private fun coverage(idx: List<Int>): Double {
        var total = 0.0
        var end = -1.0
        for (i in idx.sortedBy { x[it] }) {
            val a = maxOf(x[i], end)
            val b = x[i] + w
            if (b > a) { total += b - a; end = b }
        }
        return total / scene
    }

    @Test fun uniformMatchesNumpyLinspaceRound() {
        // numpy: np.linspace(0, 119, 8).round() -> 0 17 34 51 68 85 102 119
        assertEquals(listOf(0, 17, 34, 51, 68, 85, 102, 119), ArmSelector.uniformIndices(120, 8))
        // np.linspace(0, 9, 4).round() -> 0 3 6 9 ; np.linspace(0, 10, 4).round() -> 0 3 7 10
        assertEquals(listOf(0, 3, 6, 9), ArmSelector.uniformIndices(10, 4))
        assertEquals(listOf(0, 3, 7, 10), ArmSelector.uniformIndices(11, 4))
        assertEquals(listOf(0, 1, 2), ArmSelector.uniformIndices(3, 8))
    }

    @Test fun timeBinsTakeFirstSharpestOfEachBin() {
        val s = DoubleArray(16) { 1.0 }
        s[5] = 9.0; s[6] = 9.0; s[15] = 4.0
        // bins of 4 frames: [0,4) [4,8) [8,12) [12,16) -> first max of each: 0, 5, 8, 15
        assertEquals(listOf(0, 5, 8, 15), ArmSelector.timeBinIndices(s, 4))
    }

    @Test fun denseSamplingIsAboutTwoAndAHalfPerSecond() {
        val t = LongArray(150) { it * 33_333_333L } // 5 s at 30 fps
        val idx = ArmSelector.denseIndices(t)
        assertEquals(0, idx[0])
        assertTrue("count ${idx.size}", idx.size in 11..13) // 5 s / 0.4 s = 12.5; frame jitter can push one pick a frame later
        assertTrue(idx.zipWithNext().all { (a, b) -> t[b] - t[a] in 366_000_000L..467_000_000L })
    }

    @Test fun capIsClampedToEightToFifteen() {
        assertEquals(8, ArmSelector.clampCap(3)); assertEquals(8, ArmSelector.clampCap(8))
        assertEquals(12, ArmSelector.clampCap(12)); assertEquals(15, ArmSelector.clampCap(99))
    }

    @Test fun uniformSweepCoverageWithExactOverlap() {
        val uniform = ArmSelector.select(Arm.UNIFORM, sharp, ts, 8, exact)
        assertEquals(8, uniform.chosen.size)
        assertTrue("uniform coverage ${coverage(uniform.chosen)}", coverage(uniform.chosen) >= 0.99)
        // Step 1200/119 = 10.08 px per frame, W = 400: a frame joins while the shift is <= 200 px (overlap >= 0.5),
        // i.e. 20 frames per group, 6 groups. With equal sharpness the first (anchor) frame represents a group.
        val slow = LongArray(n) { it * 10_000_000L } // 100 fps: the 0.25 s backstop (25 frames) does not interfere here
        val overlap = ArmSelector.select(Arm.OVERLAP, sharp, slow, 8, exact)
        assertEquals(List(6) { 20 }, overlap.groups!!.map { it.size })
        assertEquals(listOf(0, 20, 40, 60, 80, 100), overlap.chosen)
        assertTrue("overlap coverage ${coverage(overlap.chosen)}", coverage(overlap.chosen) in 0.87..0.89)
    }

    @Test fun gateDropsBlurredFramesAndGroupsAreNotMergedAcrossBlur() {
        val s = sharp.copyOf()
        for (i in 40 until 50) s[i] = 10.0 // blurred burst: below 0.5 x median
        val r = ArmSelector.select(Arm.OVERLAP, s, ts, 8, exact)
        assertTrue((40 until 50).none { it in r.chosen })
        assertEquals(n - 10, r.kept!!.size)
    }

    @Test fun unreliableEstimateStartsANewGroup() {
        val allFail = { _: Int, _: Int -> Overlap(0f, false) }
        val r = ArmSelector.select(Arm.OVERLAP, sharp, ts, 8, allFail)
        assertEquals(n, r.groups!!.size) // every kept frame is its own group
        assertEquals(8, r.chosen.size)
    }

    @Test fun maxGapBackstopSplitsLongGroups() {
        val sameView = { _: Int, _: Int -> Overlap(1f, true) } // never starts a group by overlap
        val r = ArmSelector.select(Arm.OVERLAP, sharp, ts, 8, sameView)
        // 120 frames at 60 fps = 2 s; a group is cut once a frame is >= 0.25 s after its anchor (15 frames at 16.67 ms)
        assertEquals(8, r.groups!!.size)
        assertTrue(r.groups!!.all { it.size == 15 })
    }

    @Test fun sharpestOnlyIsWorseThanTheSelectedStrategiesWhenSharpnessClusters() {
        val s = DoubleArray(n) { if (it < 30) 500.0 + it else 100.0 } // the sharpest 8 are all at the start
        val sharpOnly = (0 until n).sortedByDescending { s[it] }.take(8)
        val overlap = ArmSelector.select(Arm.OVERLAP, s, ts, 8, exact)
        assertTrue(coverage(overlap.chosen) > coverage(sharpOnly) + 0.3)
    }

    @Test fun singleIsTheSharpestSingleFrame() {
        val s = sharp.copyOf(); s[77] = 900.0
        assertEquals(listOf(77), ArmSelector.select(Arm.SINGLE, s, ts, 8, exact).chosen)
    }

    @Test fun tiedScoresSpreadInTimeWithTheTemporalTieBreak() {
        // Every pair fails to match (a fast sweep over a hard scene): every score is the unknown value 0.5, so a strict '<'
        // keeps picking the earliest candidate; the temporal tie-break picks the candidate farthest from the chosen frames.
        val allFail = { _: Int, _: Int -> Overlap(0f, false) }
        val reps = (0 until n).toList()
        val earliest = Selector.farthestFirst(reps, 8, allFail, temporalTieBreak = false)
        val spread = Selector.farthestFirst(reps, 8, allFail)
        assertEquals(8, earliest.size)
        assertEquals(8, spread.size)
        assertTrue("earliest span ${earliest.max() - earliest.min()}", earliest.max() - earliest.min() <= 8)
        assertTrue("spread span ${spread.max() - spread.min()}", spread.max() - spread.min() >= n - 15)
        // The strategy uses the tie-break by default.
        assertEquals(spread.sorted(), ArmSelector.select(Arm.OVERLAP, sharp, ts, 8, allFail).chosen)
        // With no ties (exact overlaps) the tie-break changes nothing.
        val slow = LongArray(n) { it * 10_000_000L }
        val groups = ArmSelector.select(Arm.OVERLAP, sharp, slow, 8, exact)
        val reps2 = groups.groups!!.map { it.first() }
        assertEquals(Selector.farthestFirst(reps2, 8, exact, temporalTieBreak = false), Selector.farthestFirst(reps2, 8, exact))
    }

    @Test fun medianMatchesNumpy() {
        assertEquals(2.5, Selector.median(doubleArrayOf(4.0, 1.0, 2.0, 3.0)), 0.0)
        assertEquals(3.0, Selector.median(doubleArrayOf(5.0, 1.0, 3.0)), 0.0)
    }
}
