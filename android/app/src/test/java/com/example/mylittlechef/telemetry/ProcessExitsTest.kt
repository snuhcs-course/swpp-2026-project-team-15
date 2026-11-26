// AI-generated with Claude Code (Opus 5.5), 2026-11-26; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.telemetry

import com.example.mylittlechef.data.telemetry.ExitMark
import com.example.mylittlechef.data.telemetry.FileExitMark
import com.example.mylittlechef.data.telemetry.ProcessExitReport
import com.example.mylittlechef.domain.ExitKind
import com.example.mylittlechef.domain.ProcessExit
import com.example.mylittlechef.domain.Telemetry
import com.example.mylittlechef.domain.Usage
import com.example.mylittlechef.domain.UsageEvent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

/** ANRs and native crashes from Android's exit history, each sent once. */
class ProcessExitsTest {
    @get:Rule val folder = TemporaryFolder()

    private class Recorder : Telemetry {
        val events = mutableListOf<Usage>()
        override fun track(usage: Usage) { events += usage }
    }

    private class MemoryMark(var value: Long = 0) : ExitMark {
        override fun get() = value
        override fun set(value: Long) { this.value = value }
    }

    private val history = listOf(
        ProcessExit(ExitKind.NATIVE_CRASH, 300),
        ProcessExit(ExitKind.ANR, 100),
        ProcessExit(ExitKind.ANR, 200)
    )

    @Test fun newExitsBecomeEventsOldestFirstWithNoText() {
        val telemetry = Recorder()
        val mark = MemoryMark()
        ProcessExitReport.send(history, mark, telemetry, "Pixel 7 Pro", 34)
        assertEquals(listOf(UsageEvent.ANR, UsageEvent.ANR, UsageEvent.CRASH), telemetry.events.map { it.event })
        assertEquals(listOf(100L, 200L, 300L), telemetry.events.map { it.t })
        val native = telemetry.events.last()
        assertEquals("native", native.error)
        assertNull(native.where)
        assertEquals("Pixel 7 Pro", native.device)
        assertEquals(300L, mark.value)
    }

    @Test fun nothingIsSentTwice() {
        val telemetry = Recorder()
        val mark = MemoryMark(200)
        ProcessExitReport.send(history, mark, telemetry, "x", 34)
        assertEquals(listOf(300L), telemetry.events.map { it.t })
        ProcessExitReport.send(history, mark, telemetry, "x", 34)
        assertEquals(1, telemetry.events.size)
        assertEquals(300L, mark.value)
    }

    @Test fun theMarkFileSurvivesARestartAndADamagedFileMeansZero() {
        val file = folder.root.resolve(FileExitMark.NAME)
        FileExitMark(file).set(1_764_000_000_000)
        assertEquals(1_764_000_000_000, FileExitMark(file).get())
        file.writeText("garbage")
        assertEquals(0L, FileExitMark(file).get())
        assertTrue(file.exists())
    }

    @Test fun anOwnerSetPhoneNameIsCleanedToTheServersPattern() {
        val telemetry = Recorder()
        ProcessExitReport.send(history.take(1), MemoryMark(), telemetry, "홍길동의 폰", 34)
        assertTrue(Regex("^[A-Za-z0-9 ._()+-]{1,64}$").matches(telemetry.events.single().device!!))
    }
}
