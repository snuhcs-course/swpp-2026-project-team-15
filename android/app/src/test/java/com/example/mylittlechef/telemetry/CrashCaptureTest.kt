// AI-generated with Claude Code (Opus 5.5), 2026-11-26; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.telemetry

import com.example.mylittlechef.data.local.UsageDataSettings
import com.example.mylittlechef.data.local.UsageDataState
import com.example.mylittlechef.data.remote.TelemetryBatchDto
import com.example.mylittlechef.data.remote.TelemetryEventDto
import com.example.mylittlechef.data.telemetry.CrashCapture
import com.example.mylittlechef.data.telemetry.CrashStore
import com.example.mylittlechef.data.telemetry.FileCrashStore
import com.example.mylittlechef.data.telemetry.RemoteTelemetry
import com.example.mylittlechef.domain.CrashRecord
import com.example.mylittlechef.domain.Usage
import com.example.mylittlechef.domain.UsageEvent
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder
import java.io.IOException

/** Crashes of the last run, sent on the next launch (research/decisions/adr-007-telemetry.md). */
@OptIn(ExperimentalCoroutinesApi::class)
class CrashCaptureTest {
    @get:Rule val folder = TemporaryFolder()
    private var original: Thread.UncaughtExceptionHandler? = null
    private val results = mutableListOf<TelemetryEventDto>()

    @Before fun keep() { original = Thread.getDefaultUncaughtExceptionHandler() }
    @After fun restore() { Thread.setDefaultUncaughtExceptionHandler(original) }

    private fun failureInApp(message: String): Throwable {
        val root = IOException(message).apply {
            stackTrace = arrayOf(
                StackTraceElement("okhttp3.internal.Call", "execute", "Call.kt", 10),
                StackTraceElement("com.example.mylittlechef.data.DishRepo", "load", "DishRepo.kt", 42)
            )
        }
        return IllegalStateException("failed for 양파, 두부", root).apply {
            stackTrace = arrayOf(StackTraceElement("com.example.mylittlechef.ui.Screen", "show", "Screen.kt", 7))
        }
    }

    private class MemoryStore : CrashStore {
        var record: CrashRecord? = null
        override fun save(record: CrashRecord) { this.record = record }
        override fun take() = record.also { record = null }
    }

    @Test fun aRecordHoldsClassNamesAndTheFirstAppFrameOfTheRootCauseButNoMessage() {
        val record = CrashRecord.of(failureInApp("GET /dishes 양파"), "Pixel 7 Pro", 34, 1_000)
        assertEquals("java.lang.IllegalStateException", record.type)
        assertEquals("java.io.IOException", record.causeType)
        assertEquals("com.example.mylittlechef.data.DishRepo.load", record.function)
        assertEquals(42, record.line)
        assertEquals("Pixel 7 Pro", record.device)
        val stored = record.encode()
        assertFalse(stored.contains("양파") || stored.contains("dishes") || stored.contains("두부"))
    }

    @Test fun valuesAreCleanedToTheServersPatterns() {
        val failure = RuntimeException("x").apply {
            stackTrace = arrayOf(StackTraceElement("kotlin.Foo", "bar baz", null, -2))
        }
        val record = CrashRecord.of(failure, "홍길동 폰\n", 0, 5)
        assertEquals("kotlin.Foo.bar_baz", record.function) // no app frame: the top frame
        assertNull(record.line) // a native frame has no line
        assertTrue(Regex("^[A-Za-z0-9 ._()+-]{1,64}$").matches(record.device))
        assertNull(record.causeType)
        assertEquals(1, record.apiLevel)
        assertTrue(Regex("^[A-Za-z0-9_$.<>]{1,200}$").matches(record.function!!))
    }

    @Test fun theFileKeepsTheNewestCrashCountsRepeatsAndIsRemovedWhenTaken() {
        val file = folder.root.resolve(FileCrashStore.NAME)
        val store = FileCrashStore(file)
        store.save(CrashRecord.of(failureInApp("a"), "SM-S918N", 34, 1))
        store.save(CrashRecord.of(RuntimeException("b"), "SM-S918N", 34, 2))
        val taken = store.take()!!
        assertEquals("java.lang.RuntimeException", taken.type)
        assertEquals(2, taken.count)
        assertEquals(2L, taken.t)
        assertFalse(file.exists())
        assertNull(store.take())
    }

    @Test fun aDamagedFileIsDroppedQuietly() {
        val file = folder.root.resolve(FileCrashStore.NAME).apply { writeText("garbage\ntype=") }
        assertNull(FileCrashStore(file).take())
        assertFalse(file.exists())
    }

    @Test fun theHandlerStoresTheCrashThenHandsItToThePreviousHandler() {
        val store = MemoryStore()
        val seen = mutableListOf<Throwable>()
        val previous = Thread.UncaughtExceptionHandler { _, e -> seen += e }
        val handler = CrashCapture.install(store, "SM-S918N", 34, clock = { 77 }, previous = previous)
        assertSame(handler, Thread.getDefaultUncaughtExceptionHandler())
        val failure = failureInApp("m")
        handler.uncaughtException(Thread.currentThread(), failure)
        assertEquals(listOf(failure), seen)
        assertEquals(77L, store.record!!.t)
    }

    @Test fun aFailingStoreDoesNotHideTheOriginalCrash() {
        val broken = object : CrashStore {
            override fun save(record: CrashRecord) = throw IOException("disk full")
            override fun take(): CrashRecord? = null
        }
        val seen = mutableListOf<Throwable>()
        val handler = CrashCapture.install(broken, "x", 34, previous = { _, e -> seen += e })
        val failure = RuntimeException("boom")
        handler.uncaughtException(Thread.currentThread(), failure)
        assertEquals(listOf(failure), seen)
    }

    /** Emits nothing until [load]: like DataStore before the stored consent is read. */
    private class SlowSettings : UsageDataSettings {
        override val state = MutableSharedFlow<UsageDataState>(replay = 1)
        suspend fun load(value: UsageDataState) = state.emit(value)
        override suspend fun installId() = "0f8fad5b-d9cb-469f-a165-70867728950e"
        override suspend fun setEnabled(enabled: Boolean) = Unit
        override suspend fun markNoticeSeen() = Unit
    }

    private fun launchWithCrash(consent: UsageDataState) = runTest(StandardTestDispatcher()) {
        val sent = mutableListOf<TelemetryBatchDto>()
        val settings = SlowSettings()
        val telemetry = RemoteTelemetry({ sent += it }, settings, backgroundScope, "1.0.1")
        val store = MemoryStore().apply { record = CrashRecord.of(failureInApp("q"), "SM-S918N", 34, 9) }
        CrashCapture.report(store, telemetry) // at first use, before the consent has loaded
        telemetry.track(Usage(UsageEvent.SESSION_START))
        settings.load(consent)
        advanceUntilIdle(); runCurrent()
        assertNull(store.record) // removed whether or not it was sent
        results += sent.flatMap { it.events }.filter { it.name == "crash" }
    }

    /** The wire names are the OpenTelemetry attribute names; no message or stack trace field exists. */
    @Test fun theCrashGoesOutUnderOpenTelemetryNames() {
        val dto = com.example.mylittlechef.data.remote.TelemetryEventDto(
            name = "crash", t = 1, exceptionType = "a.B", exceptionCauseType = "c.D", codeFunction = "e.F.g",
            codeLine = 3, deviceModel = "SM-S918N", apiLevel = 34
        )
        val json = com.google.gson.Gson().toJson(dto)
        for (name in listOf("exception.type", "exception.cause.type", "code.function.name", "code.line.number",
            "device.model.identifier", "android.os.api_level")) assertTrue(name, json.contains("\"$name\""))
        assertFalse(json.contains("message") || json.contains("stacktrace"))
        val fields = com.example.mylittlechef.data.remote.TelemetryEventDto::class.java.declaredFields.map { it.name }
        assertFalse(fields.any { it.contains("message", ignoreCase = true) || it.contains("stack", ignoreCase = true) })
    }

    @Test fun theNextLaunchSendsTheCrashOnlyWithConsent() {
        launchWithCrash(UsageDataState(enabled = true, noticeSeen = true))
        val crash = results.single()
        assertEquals("java.lang.IllegalStateException", crash.exceptionType)
        assertEquals("com.example.mylittlechef.data.DishRepo.load", crash.codeFunction)
        assertEquals(42, crash.codeLine)
        assertEquals(34, crash.apiLevel)
        assertEquals(9L, crash.t)

        results.clear()
        launchWithCrash(UsageDataState(enabled = false, noticeSeen = true))
        assertTrue(results.isEmpty())
        launchWithCrash(UsageDataState(enabled = true, noticeSeen = false))
        assertTrue(results.isEmpty())
    }
}
