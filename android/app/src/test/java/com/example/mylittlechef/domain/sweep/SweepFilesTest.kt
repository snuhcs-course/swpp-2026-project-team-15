// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
package com.example.mylittlechef.domain.sweep

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class SweepFilesTest {
    @get:Rule
    val tmp = TemporaryFolder()

    private fun sweepDir(name: String = "sweep-1000", frames: Int = 3): File {
        val dir = tmp.newFolder(name)
        repeat(frames) { File(dir, SweepFiles.frameName(it)).writeBytes(byteArrayOf(it.toByte(), 1)) }
        return dir
    }

    @Test
    fun namesFollowTheConvention() {
        assertEquals("sweep-1730000000000", SweepFiles.directoryName(1730000000000))
        assertEquals("frame-00.jpg", SweepFiles.frameName(0))
        assertEquals("frame-14.jpg", SweepFiles.frameName(14))
    }

    @Test
    fun theWholeSweepIsFoundFromThePreviewFramePreviewFirst() {
        val dir = sweepDir(frames = 4)
        val frames = SweepFiles.framesFor(File(dir, "frame-00.jpg"))!!
        assertEquals(listOf("frame-00.jpg", "frame-01.jpg", "frame-02.jpg", "frame-03.jpg"), frames.map { it.name })
    }

    @Test
    fun aSingleFrameIsNotASweep() {
        assertNull(SweepFiles.framesFor(File(sweepDir(frames = 1), "frame-00.jpg")))
    }

    @Test
    fun ordinaryPhotosAndOtherFramesAreNotSweeps() {
        val dir = sweepDir()
        val photo = File(tmp.root, "capture_123.jpg").apply { writeBytes(byteArrayOf(1)) }
        assertNull(SweepFiles.framesFor(photo))
        assertNull(SweepFiles.framesFor(File(dir, "frame-01.jpg")))
        val wrongFolder = sweepDir("pictures", frames = 3)
        assertNull(SweepFiles.framesFor(File(wrongFolder, "frame-00.jpg")))
    }

    @Test
    fun aGapStopsTheSweepAtTheFirstMissingFrame() {
        val dir = sweepDir(frames = 4)
        File(dir, "frame-02.jpg").delete()
        assertEquals(2, SweepFiles.framesFor(File(dir, "frame-00.jpg"))!!.size)
    }

    @Test
    fun staleSweepFoldersAreDeletedAndOthersKept() {
        val old = sweepDir("sweep-1").apply { setLastModified(1_000) }
        val fresh = sweepDir("sweep-2").apply { setLastModified(9_500) }
        val unrelated = tmp.newFolder("image_cache").apply { setLastModified(0) }
        SweepFiles.deleteStale(tmp.root, nowMs = 10_000, maxAgeMs = 1_000)
        assertFalse(old.exists())
        assertTrue(fresh.exists())
        assertTrue(unrelated.exists())
    }
}
