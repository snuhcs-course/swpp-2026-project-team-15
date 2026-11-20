// AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.telemetry

import com.example.mylittlechef.data.local.UsageDataSettings
import com.example.mylittlechef.data.local.UsageDataState
import com.example.mylittlechef.data.remote.TelemetryBatchDto
import com.example.mylittlechef.data.telemetry.RemoteTelemetry
import com.example.mylittlechef.data.telemetry.SessionTracker
import com.example.mylittlechef.domain.Telemetry
import com.example.mylittlechef.domain.Usage
import com.example.mylittlechef.domain.UsageEvent
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test

/** Integrity review (2026-11-20): the cold start's session_start and rotations. */
@OptIn(ExperimentalCoroutinesApi::class)
class TelemetryLifecycleTest {
    /** Emits nothing until [load]: like DataStore before the stored consent is read. */
    private class SlowSettings : UsageDataSettings {
        override val state = MutableSharedFlow<UsageDataState>(replay = 1)
        suspend fun load(value: UsageDataState) = state.emit(value)
        override suspend fun installId() = "0f8fad5b-d9cb-469f-a165-70867728950e"
        override suspend fun setEnabled(enabled: Boolean) = Unit
        override suspend fun markNoticeSeen() = Unit
    }

    private class Recorder : Telemetry {
        val events = mutableListOf<UsageEvent>()
        override fun track(usage: Usage) { events += usage.event }
    }

    @Test fun anEventBeforeTheConsentIsReadIsSentOnceItAllows() = runTest(StandardTestDispatcher()) {
        val sent = mutableListOf<TelemetryBatchDto>()
        val settings = SlowSettings()
        val telemetry = RemoteTelemetry({ sent += it }, settings, backgroundScope, "1.0")
        runCurrent()
        telemetry.track(Usage(UsageEvent.SESSION_START))
        settings.load(UsageDataState(enabled = true, noticeSeen = true))
        advanceUntilIdle(); runCurrent()
        telemetry.flush()
        advanceUntilIdle(); runCurrent()
        assertEquals(listOf("session_start"), sent.flatMap { it.events.map { e -> e.name } })
    }

    @Test fun anEventBeforeTheConsentIsReadIsDroppedWhenItDoesNot() = runTest(StandardTestDispatcher()) {
        val sent = mutableListOf<TelemetryBatchDto>()
        val settings = SlowSettings()
        val telemetry = RemoteTelemetry({ sent += it }, settings, backgroundScope, "1.0")
        runCurrent()
        telemetry.track(Usage(UsageEvent.SESSION_START))
        settings.load(UsageDataState(enabled = false, noticeSeen = true))
        advanceUntilIdle(); runCurrent()
        telemetry.flush()
        advanceUntilIdle(); runCurrent()
        assertEquals(emptyList<TelemetryBatchDto>(), sent)
    }

    @Test fun aRotationDoesNotEndTheSession() {
        val recorder = Recorder()
        var now = 1_000L
        val sessions = SessionTracker { now }
        sessions.onStart(recorder)
        now += 5_000
        sessions.onStop(recorder, changingConfigurations = true) // rotation: activity rebuilt
        sessions.onStart(recorder)
        now += 5_000
        sessions.onStop(recorder, changingConfigurations = false) // to the background
        assertEquals(listOf(UsageEvent.SESSION_START, UsageEvent.SESSION_END), recorder.events)
    }
}
