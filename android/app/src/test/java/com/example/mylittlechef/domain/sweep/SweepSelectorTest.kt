// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.domain.sweep

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class SweepSelectorTest {
    private val second = 1_000_000_000L

    /** Feeds [sharpness] values at 10 frames per second over a 5 s sweep (5 frames per bin). */
    private fun run(vararg sharpness: Double): SweepSelector.Result? {
        val selector = SweepSelector(5 * second, 10)
        sharpness.forEachIndexed { i, s -> selector.offer(i * second / 10, s) }
        return selector.finish()
    }

    /** One frame per 0.5 s bin. */
    private fun onePerBin(vararg sharpness: Double): SweepSelector.Result? {
        val selector = SweepSelector(5 * second, 10)
        sharpness.forEachIndexed { i, s -> selector.offer(i * second / 2, s) }
        return selector.finish()
    }

    @Test
    fun keepsTheSharpestFramePerTimeBinAndSpreadsOverTheSweep() {
        // 50 frames; frame 3 + 5k is the sharpest of every 5-frame (0.5 s) bin.
        val values = DoubleArray(50) { if (it % 5 == 3) 100.0 else 80.0 }
        val result = run(*values)!!
        assertEquals(List(10) { 3 + 5 * it }, result.indices)
        assertFalse(result.singleFrameFallback)
    }

    @Test
    fun neverKeepsMoreThanTheBinCount() {
        val selector = SweepSelector(5 * second, 10)
        repeat(300) { selector.offer(it * second / 60, (it % 7).toDouble() + 1) }
        assertTrue(selector.held().size <= 10)
    }

    @Test
    fun offerTellsTheCallerWhichFrameToRelease() {
        val selector = SweepSelector(5 * second, 10)
        val first = selector.offer(0, 10.0)
        val second = selector.offer(1_000_000, 20.0) // same bin, sharper
        val third = selector.offer(2_000_000, 15.0) // same bin, duller
        assertTrue(first.keep && first.release == null)
        assertTrue(second.keep)
        assertEquals(0, second.release)
        assertFalse(third.keep)
        assertEquals(listOf(1), selector.held())
    }

    @Test
    fun blurredFramesAreDroppedByTheGate() {
        // 10 bins: nine at sharpness 100 and one at 10 (< half of the median 100).
        val values = DoubleArray(10) { if (it == 4) 10.0 else 100.0 }
        val result = onePerBin(*values)!!
        assertFalse(4 in result.indices)
        assertEquals(9, result.indices.size)
    }

    @Test
    fun theRepresentativeIsTheSharpestChosenFrame() {
        val values = DoubleArray(10) { 100.0 }.also { it[6] = 150.0 }
        assertEquals(6, onePerBin(*values)!!.representative)
    }

    @Test
    fun fallsBackToTheSharpestSingleFrameWhenTooFewSurvive() {
        // One usable frame only.
        val result = onePerBin(90.0)!!
        assertEquals(listOf(0), result.indices)
        assertEquals(0, result.representative)
        assertTrue(result.singleFrameFallback)
    }

    @Test
    fun aUniformSweepKeepsEveryBin() {
        // A black scene scores 0 everywhere; zero is not "below half of zero", so frames pass.
        val result = onePerBin(*DoubleArray(10) { 0.0 })!!
        assertEquals(10, result.indices.size)
    }

    @Test
    fun emptySweepHasNoResult() {
        assertNull(SweepSelector(5 * second, 10).finish())
    }

    @Test
    fun framesOutsideTheSweepAreClampedIntoTheEdgeBins() {
        val selector = SweepSelector(5 * second, 10)
        selector.offer(-5, 1.0)
        selector.offer(9 * second, 2.0)
        assertEquals(listOf(0, 1), selector.held())
    }

    @Test(expected = IllegalArgumentException::class)
    fun binCountAboveTheServerLimitIsRejected() {
        SweepSelector(5 * second, SweepSelector.MAX_FRAMES + 1)
    }
}
