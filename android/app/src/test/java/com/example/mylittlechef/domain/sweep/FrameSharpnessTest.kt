// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.domain.sweep

import java.nio.ByteBuffer
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class FrameSharpnessTest {
    private fun image(width: Int, height: Int, value: (Int, Int) -> Int) =
        GrayImage(width, height, IntArray(width * height) { value(it % width, it / width) })

    @Test
    fun flatImageHasZeroSharpness() {
        assertEquals(0.0, FrameSharpness.laplacianVariance(image(32, 32) { _, _ -> 120 }), 0.0)
    }

    @Test
    fun tinyImageHasZeroSharpness() {
        assertEquals(0.0, FrameSharpness.laplacianVariance(image(2, 2) { x, y -> x * 100 + y }), 0.0)
    }

    @Test
    fun checkerboardMatchesTheHandComputedValue() {
        // Every interior pixel has four neighbours of the opposite value: laplacian = +-4 * 255.
        val checker = image(8, 8) { x, y -> if ((x + y) % 2 == 0) 0 else 255 }
        val laplacianSquared = (4.0 * 255) * (4.0 * 255)
        // Laplacian alternates +1020 / -1020 over 36 interior pixels: mean 0, variance 1020^2.
        assertEquals(laplacianSquared, FrameSharpness.laplacianVariance(checker), 1e-6)
    }

    @Test
    fun blurringLowersTheScore() {
        val sharp = image(64, 64) { x, y -> if ((x / 4 + y / 4) % 2 == 0) 0 else 255 }
        val blurred = boxBlur(sharp)
        assertTrue(FrameSharpness.laplacianVariance(blurred) < FrameSharpness.laplacianVariance(sharp))
    }

    @Test
    fun samplingHonoursRowAndPixelStride() {
        // 6x4 luma plane padded to rowStride 8 with 0xFF filler that must never be read.
        val plane = ByteArray(8 * 4) { 0xFF.toByte() }
        for (y in 0 until 4) for (x in 0 until 6) plane[y * 8 + x] = (y * 10 + x).toByte()
        val gray = FrameSharpness.sampleLuma(ByteBuffer.wrap(plane), 8, 1, 6, 4, side = 256)
        assertEquals(6, gray.width)
        assertEquals(4, gray.height)
        assertEquals(23, gray.pixels[2 * 6 + 3])
        assertTrue(gray.pixels.none { it == 255 })
    }

    @Test
    fun samplingShrinksTheLongSideToAboutTheTarget() {
        val plane = ByteArray(1280 * 720)
        val gray = FrameSharpness.sampleLuma(ByteBuffer.wrap(plane), 1280, 1, 1280, 720)
        // step = 1280 / 256 = 5, so the sample is 256 x 144.
        assertEquals(256, gray.width)
        assertEquals(144, gray.height)
    }

    private fun boxBlur(src: GrayImage): GrayImage {
        val out = IntArray(src.pixels.size)
        for (y in 0 until src.height) for (x in 0 until src.width) {
            var sum = 0
            var n = 0
            for (dy in -2..2) for (dx in -2..2) {
                val xx = x + dx
                val yy = y + dy
                if (xx in 0 until src.width && yy in 0 until src.height) {
                    sum += src.pixels[yy * src.width + xx]
                    n++
                }
            }
            out[y * src.width + x] = sum / n
        }
        return GrayImage(src.width, src.height, out)
    }
}
