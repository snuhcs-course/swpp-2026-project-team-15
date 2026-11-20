// AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data.telemetry

import com.example.mylittlechef.data.local.UsageDataSettings
import com.example.mylittlechef.data.local.UsageDataState
import com.example.mylittlechef.data.remote.TelemetryBatchDto
import com.example.mylittlechef.data.remote.TelemetryEventDto
import com.example.mylittlechef.domain.Telemetry
import com.example.mylittlechef.domain.Usage
import com.example.mylittlechef.domain.UsageEvent
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.launch
import java.util.UUID

/**
 * Buffers events in memory and posts them in batches, best effort: a failed post is dropped, never retried,
 * so a bad connection costs nothing but data. Nothing is buffered while sending is off.
 */
class RemoteTelemetry(
    private val send: suspend (TelemetryBatchDto) -> Unit,
    private val settings: UsageDataSettings,
    private val scope: CoroutineScope,
    private val appVersion: String,
    private val batchSize: Int = 20
) : Telemetry {
    @Volatile private var state = UsageDataState()
    @Volatile private var sessionId = UUID.randomUUID().toString()
    private val buffer = mutableListOf<Usage>()

    init {
        scope.launch {
            settings.state.collect {
                state = it
                if (!it.sending) synchronized(buffer) { buffer.clear() }
            }
        }
    }

    override fun track(usage: Usage) {
        if (!state.sending) return
        if (usage.event == UsageEvent.SESSION_START) {
            flush() // the previous session's events leave with its own id
            sessionId = UUID.randomUUID().toString()
        }
        val full = synchronized(buffer) {
            buffer.add(usage)
            buffer.size >= batchSize
        }
        if (full) flush()
    }

    override fun flush() {
        val session = sessionId
        val events = synchronized(buffer) { buffer.toList().also { buffer.clear() } }
        if (events.isEmpty()) return
        scope.launch {
            try {
                if (!state.sending) return@launch
                send(TelemetryBatchDto(settings.installId(), session, appVersion, events.map(::toDto)))
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                // usage data is not worth a retry or an error on screen
            }
        }
    }

    private fun toDto(usage: Usage) = TelemetryEventDto(
        name = usage.event.wire,
        t = usage.t,
        dishId = usage.dishId,
        count = usage.count,
        durationMs = usage.durationMs,
        status = usage.status,
        source = usage.source,
        screen = usage.screen,
        code = usage.code
    )
}
