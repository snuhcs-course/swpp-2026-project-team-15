// AI-generated with Claude Code (Opus 5.5), 2026-11-26; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data.telemetry

import android.app.ActivityManager
import android.app.ApplicationExitInfo
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import com.example.mylittlechef.domain.ExitKind
import com.example.mylittlechef.domain.ProcessExit
import com.example.mylittlechef.domain.Telemetry
import com.example.mylittlechef.domain.exitEvents
import java.io.File

/** The time of the newest exit already turned into an event, so none is sent twice. */
interface ExitMark {
    fun get(): Long
    fun set(value: Long)
}

class FileExitMark(private val file: File) : ExitMark {
    override fun get(): Long = try { file.readText().trim().toLong() } catch (_: Exception) { 0L }
    override fun set(value: Long) { file.writeText(value.toString()) }

    companion object {
        const val NAME = "last-exit-reported.txt"
    }
}

/**
 * Reads Android's record of past exits on API 30+ (older phones report nothing) and tracks an `anr` or a
 * native `crash` event for each new one. Consent is decided by RemoteTelemetry, as for crashes; the mark moves
 * on either way. Only [ApplicationExitInfo.getReason] and [ApplicationExitInfo.getTimestamp] are read.
 */
object ProcessExitReport {
    private const val HISTORY = 16

    fun report(context: Context, mark: ExitMark, telemetry: Telemetry, device: String = Build.MODEL.orEmpty()) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return
        try {
            val manager = context.getSystemService(ActivityManager::class.java) ?: return
            val exits = manager.getHistoricalProcessExitReasons(context.packageName, 0, HISTORY).mapNotNull {
                when (it.reason) {
                    ApplicationExitInfo.REASON_ANR -> ProcessExit(ExitKind.ANR, it.timestamp)
                    ApplicationExitInfo.REASON_CRASH_NATIVE -> ProcessExit(ExitKind.NATIVE_CRASH, it.timestamp)
                    else -> null // REASON_CRASH: the in-app handler already kept it
                }
            }
            send(exits, mark, telemetry, device, Build.VERSION.SDK_INT, installedAt(context))
        } catch (_: Exception) {
            // usage data is never worth a failed start
        }
    }

    /**
     * The part without Android, for tests. Exits from before [installedAt] (this version's install or update
     * time) are skipped: Android keeps the history across updates, and an older build's freeze must not be
     * counted against this version on its first launch.
     */
    fun send(exits: List<ProcessExit>, mark: ExitMark, telemetry: Telemetry, device: String, sdk: Int, installedAt: Long = 0L) {
        val (events, newest) = exitEvents(exits, maxOf(mark.get(), installedAt), device, sdk)
        events.forEach(telemetry::track)
        if (events.isNotEmpty()) mark.set(newest)
    }

    /** When this version was installed or last updated; 0 when unknown, which keeps the whole history. */
    private fun installedAt(context: Context): Long = try {
        val name = context.packageName
        val info = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)
            context.packageManager.getPackageInfo(name, PackageManager.PackageInfoFlags.of(0))
        else @Suppress("DEPRECATION") context.packageManager.getPackageInfo(name, 0)
        info.lastUpdateTime
    } catch (_: Exception) {
        0L
    }
}
