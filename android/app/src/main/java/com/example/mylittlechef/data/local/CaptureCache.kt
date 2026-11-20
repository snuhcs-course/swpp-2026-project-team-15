// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data.local

import java.io.File

/** Removes what the capture screens leave in the app cache: single photos and sweep folders. */
object CaptureCache {
    private val PHOTO = Regex("""capture_\d+\.jpg""")
    private val SWEEP = Regex("""sweep-\d+""")

    /** Deletes cache/capture_<millis>.jpg files and cache/sweep-<millis>/ folders; returns how many were removed. */
    fun clear(cacheDir: File): Int {
        var removed = 0
        cacheDir.listFiles()?.forEach { entry ->
            val matches = (entry.isFile && PHOTO.matches(entry.name)) || (entry.isDirectory && SWEEP.matches(entry.name))
            if (matches && entry.deleteRecursively()) removed++
        }
        return removed
    }
}
