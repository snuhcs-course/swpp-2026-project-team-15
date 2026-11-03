// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
package com.mylittlechef.researchdemo

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.Random
import kotlin.math.abs

/** Known-answer checks of the streaming selector on the same 1-D sweep model as ArmSelectorTest. */
class LiveSelectorTest {
    private val n = 120
    private val w = 400.0
    private val scene = 1600.0
    private val x = DoubleArray(n) { it * (scene - w) / (n - 1) }
    private val ts = LongArray(n) { it * 16_666_667L }
    private val exact = { a: Int, b: Int -> Overlap(maxOf(0.0, 1 - abs(x[a] - x[b]) / w).toFloat(), true) }

    private fun coverage(idx: List<Int>): Double {
        var total = 0.0; var end = -1.0
        for (i in idx.sortedBy { x[it] }) {
            val a = maxOf(x[i], end); val b = x[i] + w
            if (b > a) { total += b - a; end = b }
        }
        return total / scene
    }

    private fun live(sharp: DoubleArray, cap: Int, maxReps: Int = LiveSelector.DEFAULT_MAX_REPS): Pair<List<Int>, LiveSelector> {
        val sel = LiveSelector(cap, maxReps = maxReps, pair = exact)
        for (i in 0 until n) sel.push(i, ts[i], sharp[i])
        return sel.finish() to sel
    }

    @Test fun equalsOfflineOverlapStrategyWhenTheTwoGatesAgree() {
        // Constant sharpness: every frame passes both gates.
        val flat = DoubleArray(n) { 100.0 }
        for (cap in 8..15) {
            val off = ArmSelector.select(Arm.OVERLAP, flat, ts, cap, exact).chosen
            assertEquals("cap=$cap", off, live(flat, cap).first)
        }
        // Blurred frames after a warm-up: running median == final median at every decision, so both gates reject the same frames.
        val rnd = Random(7)
        val s = DoubleArray(n) { 90.0 + rnd.nextInt(21) }
        for (i in intArrayOf(15, 16, 40, 41, 42, 77, 95)) s[i] = 5.0
        for (cap in intArrayOf(8, 12, 15)) {
            val off = ArmSelector.select(Arm.OVERLAP, s, ts, cap, exact)
            val (got, sel) = live(s, cap)
            val offGate = Selector.gate(s, Selector.GATE_RATIO)
            assertEquals("gate decisions", offGate.toList(), sel.gateLog)
            assertEquals("cap=$cap", off.chosen, got)
        }
    }

    @Test fun capIsRespectedAndCoverageStaysHigh() {
        val flat = DoubleArray(n) { 100.0 }
        val (got, _) = live(flat, 8)
        assertEquals(8, got.size)
        assertTrue("coverage ${coverage(got)}", coverage(got) >= 0.75)
    }

    @Test fun memoryIsBoundedByMaxRepsNotByClipLength() {
        val flat = DoubleArray(n) { 100.0 }
        val (got, sel) = live(flat, 8, maxReps = 4)
        assertTrue("retained ${sel.maxRetained}", sel.maxRetained <= 4 + 3) // reps + anchor + best + the frame being pushed
        assertTrue(sel.merges > 0)
        assertEquals(8.coerceAtMost(got.size), got.size)
        assertTrue("coverage ${coverage(got)}", coverage(got) >= 0.5)
        // Everything not chosen has been released.
        assertTrue(sel.heldFrames().all { it in got })
    }

    @Test fun releasedFramesAreReleasedExactlyOnce() {
        val released = HashMap<Int, Int>()
        val flat = DoubleArray(n) { 100.0 }
        val sel = LiveSelector(8, pair = exact, release = { released.merge(it, 1, Int::plus) })
        for (i in 0 until n) sel.push(i, ts[i], flat[i])
        val chosen = sel.finish()
        assertTrue(released.values.all { it == 1 })
        assertTrue(released.keys.none { it in chosen })
        assertEquals(n - chosen.size, released.size)
    }

    @Test fun anUnreliableEstimateStartsANewGroup() {
        val flat = DoubleArray(10) { 100.0 }
        val sel = LiveSelector(8, pair = { _, _ -> Overlap(0.9f, false) })
        for (i in 0 until 10) sel.push(i, i * 1_000_000L, flat[i])
        sel.finish()
        assertEquals(10, sel.groupsClosed) // every frame its own group
    }

    @Test fun blurredFirstFrameIsAKnownDifferenceFromTheOfflineGate() {
        // Documented limit: with a blurred first frame the running median is that frame itself, so it passes the live gate.
        val s = DoubleArray(n) { 100.0 }; s[0] = 1.0
        val sel = LiveSelector(8, pair = exact)
        sel.push(0, ts[0], s[0])
        assertEquals(listOf(true), sel.gateLog)
        assertEquals(false, Selector.gate(s)[0])
    }
}
