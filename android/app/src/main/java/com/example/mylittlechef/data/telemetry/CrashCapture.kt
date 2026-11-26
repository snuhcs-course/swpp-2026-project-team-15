// AI-generated with Claude Code (Opus 5.5), 2026-11-26; human review pending.
package com.example.mylittlechef.data.telemetry

import com.example.mylittlechef.domain.CrashRecord
import com.example.mylittlechef.domain.Telemetry
import java.io.File

/** Where the last run's crash waits for the next launch. One record; [take] reads and removes it. */
interface CrashStore {
    fun save(record: CrashRecord)
    fun take(): CrashRecord?
}

/** A small file in app-private storage, written synchronously from the dying thread. */
class FileCrashStore(private val file: File) : CrashStore {
    override fun save(record: CrashRecord) {
        val previous = read()
        val kept = record.copy(count = ((previous?.count ?: 0) + 1).coerceAtMost(10_000))
        file.writeText(kept.encode())
    }

    override fun take(): CrashRecord? {
        val record = read()
        file.delete()
        return record
    }

    private fun read(): CrashRecord? = try {
        if (file.isFile) CrashRecord.decode(file.readText()) else null
    } catch (_: Exception) {
        null
    }

    companion object {
        const val NAME = "last-crash.txt"
    }
}

/**
 * Uncaught exceptions of the app process (research/decisions/adr-007-telemetry.md). [install] runs once at
 * process start; [report] once the usage sender exists, so the crash goes out with the next session's batch
 * if, and only if, the stored consent allows sending (RemoteTelemetry decides; the file is removed either way).
 */
object CrashCapture {
    fun install(
        store: CrashStore,
        device: String,
        sdk: Int,
        clock: () -> Long = System::currentTimeMillis,
        previous: Thread.UncaughtExceptionHandler? = Thread.getDefaultUncaughtExceptionHandler()
    ): Thread.UncaughtExceptionHandler {
        val handler = Thread.UncaughtExceptionHandler { thread, failure ->
            try {
                store.save(CrashRecord.of(failure, device, sdk, clock()))
            } catch (_: Throwable) {
                // never hide the original crash behind one of our own
            }
            previous?.uncaughtException(thread, failure)
        }
        Thread.setDefaultUncaughtExceptionHandler(handler)
        return handler
    }

    fun report(store: CrashStore, telemetry: Telemetry) {
        val record = try { store.take() } catch (_: Exception) { null } ?: return
        telemetry.track(record.toUsage())
    }
}
