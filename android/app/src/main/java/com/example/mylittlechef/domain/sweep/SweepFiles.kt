// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.domain.sweep

import java.io.File

/**
 * On-disk convention that links the capture screen to the uploader without a new navigation
 * argument: the capture screen hands over one URI (the preview frame), and the uploader finds the
 * other frames of the same sweep next to it.
 *
 *   <cache>/sweep-<millis>/frame-00.jpg   preview frame (the sharpest chosen frame)
 *   <cache>/sweep-<millis>/frame-01.jpg   remaining chosen frames, in time order
 *
 * A file counts as a sweep only when it is `frame-00.jpg` inside a `sweep-<digits>` folder, so
 * ordinary photos and gallery picks never match.
 */
object SweepFiles {
    private val DIR = Regex("""sweep-\d+""")

    fun directoryName(startMillis: Long) = "sweep-$startMillis"

    fun frameName(position: Int): String {
        require(position in 0 until SweepSelector.MAX_FRAMES) { "position out of range" }
        return "frame-%02d.jpg".format(position)
    }

    /**
     * All frames of the sweep that [preview] belongs to, preview first, or null when [preview]
     * is not a sweep preview or fewer than two consecutive frames exist.
     */
    fun framesFor(preview: File): List<File>? {
        val dir = preview.parentFile ?: return null
        if (preview.name != frameName(0) || !DIR.matches(dir.name)) return null
        val frames = generateSequence(0) { it + 1 }
            .takeWhile { it < SweepSelector.MAX_FRAMES }
            .map { File(dir, frameName(it)) }
            .takeWhile { it.isFile && it.length() > 0 }
            .toList()
        return frames.takeIf { it.size >= 2 }
    }

    /** Delete sweep folders last modified more than [maxAgeMs] before [nowMs]. */
    fun deleteStale(cacheDir: File, nowMs: Long, maxAgeMs: Long) {
        cacheDir.listFiles { f -> f.isDirectory && DIR.matches(f.name) }?.forEach { dir ->
            if (nowMs - dir.lastModified() > maxAgeMs) dir.deleteRecursively()
        }
    }
}
