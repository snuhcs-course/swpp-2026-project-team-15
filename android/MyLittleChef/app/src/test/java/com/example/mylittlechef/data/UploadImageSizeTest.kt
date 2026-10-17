// AI-generated with Claude Code (Opus 5.5), 2026-10-14; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data

import org.junit.Assert.assertEquals
import org.junit.Test

class UploadImageSizeTest {
    @Test
    fun fitWithin_smallPhoto_keepsSize() {
        assertEquals(2048 to 1536, fitWithin(2048, 1536, MAX_UPLOAD_SIDE))
    }

    @Test
    fun fitWithin_landscapePhoto_shrinksLongSideTo2048() {
        assertEquals(2048 to 1536, fitWithin(4000, 3000, MAX_UPLOAD_SIDE))
    }

    @Test
    fun fitWithin_portraitPhoto_shrinksLongSideTo2048() {
        assertEquals(1999 to 2048, fitWithin(2928, 3000, MAX_UPLOAD_SIDE))
    }

    @Test
    fun sampleSizeFor_neverDecodesBelowTarget() {
        assertEquals(1, sampleSizeFor(4000, 3000, 2048, 1536))
        assertEquals(2, sampleSizeFor(8160, 6120, 2048, 1536))
    }
}
