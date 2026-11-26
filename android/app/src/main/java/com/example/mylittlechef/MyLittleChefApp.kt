// AI-generated with Claude Code (Opus 5.5), 2026-11-26; reviewed by Jaehyuk Choi.
package com.example.mylittlechef

import android.app.Application
import android.os.Build
import com.example.mylittlechef.data.telemetry.CrashCapture
import com.example.mylittlechef.data.telemetry.FileCrashStore
import java.io.File

/** The earliest hook of the process: crashes are kept from here on, before any screen exists. */
class MyLittleChefApp : Application() {
    override fun onCreate() {
        super.onCreate()
        CrashCapture.install(FileCrashStore(File(filesDir, FileCrashStore.NAME)), Build.MODEL.orEmpty(), Build.VERSION.SDK_INT)
    }
}
