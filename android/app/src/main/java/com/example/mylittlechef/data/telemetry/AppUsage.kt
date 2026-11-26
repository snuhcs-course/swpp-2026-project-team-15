// AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
// Modified with Claude Code (Opus 5.5), 2026-11-26: the last run's crash, ANRs and native crashes are reported once the sender exists;
// the last events are kept in memory for a future problem report.
package com.example.mylittlechef.data.telemetry

import android.content.Context
import android.os.Build
import com.example.mylittlechef.BuildConfig
import com.example.mylittlechef.data.local.PreferencesUsageDataSettings
import com.example.mylittlechef.data.local.localDataStore
import com.example.mylittlechef.data.remote.DishApiClient
import com.example.mylittlechef.domain.ProblemReportInfo
import com.example.mylittlechef.domain.RecentUsage
import com.example.mylittlechef.domain.RecordingTelemetry
import com.example.mylittlechef.domain.Telemetry
import com.example.mylittlechef.domain.Usage
import com.example.mylittlechef.domain.UsageEvent
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import java.io.File

/**
 * The usage sender and the session tracker of the app process, made once on first use. Only the composition
 * root (AppNavHost) asks for them and hands them on; ViewModels get them injected. The sender's scope lives as
 * long as the process, so ViewModels that survive a rotation keep a working sender.
 */
object AppUsage {
    @Volatile private var telemetry: Telemetry? = null
    val sessions = SessionTracker()
    /** The last tracked event names and screens, in memory only, for a future "문제 신고". */
    val recent = RecentUsage()

    fun telemetry(context: Context): Telemetry = telemetry ?: synchronized(this) {
        telemetry ?: RecordingTelemetry(
            RemoteTelemetry(
                DishApiClient.telemetryApi::send,
                PreferencesUsageDataSettings(context.applicationContext.localDataStore),
                CoroutineScope(SupervisorJob() + Dispatchers.IO),
                BuildConfig.VERSION_NAME
            ),
            recent
        ).also {
            telemetry = it
            // Sent with the first batch only if the stored consent allows it; the file goes either way.
            val files = context.applicationContext.filesDir
            CrashCapture.report(FileCrashStore(File(files, FileCrashStore.NAME)), it)
            ProcessExitReport.report(context.applicationContext, FileExitMark(File(files, FileExitMark.NAME)), it)
        }
    }

    /** What a "문제 신고" form is pre-filled with (prefilledReportUrl); no network, no UI. */
    fun problemReport(): ProblemReportInfo =
        ProblemReportInfo.of(BuildConfig.VERSION_NAME, Build.MODEL.orEmpty(), Build.VERSION.SDK_INT, recent)
}

/** A session is the time the app is in the foreground; an activity rebuilt by a rotation does not end it. */
class SessionTracker(private val clock: () -> Long = System::currentTimeMillis) {
    private var started = 0L
    private var rebuilding = false

    fun onStart(telemetry: Telemetry) {
        if (rebuilding) { rebuilding = false; return }
        started = clock()
        telemetry.track(Usage(UsageEvent.SESSION_START))
    }

    fun onStop(telemetry: Telemetry, changingConfigurations: Boolean) {
        if (changingConfigurations) { rebuilding = true; return }
        val length = if (started > 0) clock() - started else null
        telemetry.track(Usage(UsageEvent.SESSION_END, durationMs = length))
        telemetry.flush()
    }
}
