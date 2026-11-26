// AI-generated with Claude Code (Opus 5.5), 2026-11-26; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.domain

/**
 * Past exits of the app process that the in-app crash handler cannot see: the app frozen (ANR) and crashes in
 * native code. Android keeps them (API 30+); only the kind and the time are used, never the description or
 * the trace, which can contain text (research/decisions/adr-007-telemetry.md).
 */
enum class ExitKind { ANR, NATIVE_CRASH }

data class ProcessExit(val kind: ExitKind, val timestamp: Long)

/** The events for exits after [lastReported], oldest first, and the new mark (unchanged when none). */
fun exitEvents(exits: List<ProcessExit>, lastReported: Long, device: String, sdk: Int): Pair<List<Usage>, Long> {
    val fresh = exits.filter { it.timestamp > lastReported }.sortedBy { it.timestamp }
    val clean = CrashRecord.cleanDevice(device)
    val events = fresh.map {
        when (it.kind) {
            ExitKind.ANR -> Usage(UsageEvent.ANR, device = clean, sdk = sdk.coerceIn(1, 99), t = it.timestamp)
            ExitKind.NATIVE_CRASH -> Usage(
                UsageEvent.CRASH, error = "native", device = clean, sdk = sdk.coerceIn(1, 99), count = 1, t = it.timestamp
            )
        }
    }
    return events to (fresh.maxOfOrNull { it.timestamp } ?: lastReported)
}
