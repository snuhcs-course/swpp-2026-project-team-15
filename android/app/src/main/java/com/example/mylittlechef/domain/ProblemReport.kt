// AI-generated with Claude Code (Opus 5.5), 2026-11-26; human review pending.
package com.example.mylittlechef.domain

import java.net.URLEncoder

/**
 * The headless part of a future "문제 신고" button: the facts a bug report needs that a tester cannot easily
 * type (app version, phone model, Android API level, the last few things the app recorded), handed to our
 * Google Form as pre-filled URL parameters. The tester sees them in the form and decides whether to submit;
 * free text and screenshots go to the form only, never to our server. Nothing here touches the network.
 */
class RecentUsage(private val capacity: Int = 10) {
    private val items = ArrayDeque<String>()

    /** Event names and screens only; no dish id, status detail or other field is kept. */
    fun add(usage: Usage) {
        val label = usage.event.wire + (usage.screen?.let { ":$it" } ?: "")
        synchronized(items) {
            items.addLast(label)
            while (items.size > capacity) items.removeFirst()
        }
    }

    /** Oldest first. */
    fun labels(): List<String> = synchronized(items) { items.toList() }
}

/** A [Telemetry] that also remembers the last events in memory (for [ProblemReportInfo]), whatever the consent. */
class RecordingTelemetry(private val inner: Telemetry, private val recent: RecentUsage) : Telemetry {
    override fun track(usage: Usage) {
        recent.add(usage)
        inner.track(usage)
    }

    override fun flush() = inner.flush()
}

data class ProblemReportInfo(val appVersion: String, val device: String, val apiLevel: Int, val recent: List<String>) {
    companion object {
        fun of(appVersion: String, device: String, apiLevel: Int, recent: RecentUsage) = ProblemReportInfo(
            appVersion, CrashRecord.cleanDevice(device), CrashRecord.cleanApiLevel(apiLevel), recent.labels()
        )
    }
}

/**
 * Where the form lives and which of its questions take each value: `entry.<number>` ids from the form's
 * "Get pre-filled link". Kept as configuration, not in this file, so the form can change without code.
 */
data class ReportFormConfig(
    val baseUrl: String,
    val versionEntry: String,
    val deviceEntry: String,
    val apiLevelEntry: String,
    val recentEntry: String
)

private val ENTRY = Regex("^entry\\.[0-9]{1,20}$")

/** The form's address with the values pre-filled; null when the configuration is not a usable form address. */
fun prefilledReportUrl(config: ReportFormConfig, info: ProblemReportInfo): String? {
    val base = config.baseUrl.trim()
    if (!base.startsWith("https://") || base.any { it == '?' || it == '#' || it.isWhitespace() }) return null
    val entries = listOf(config.versionEntry, config.deviceEntry, config.apiLevelEntry, config.recentEntry)
    if (entries.any { !ENTRY.matches(it) }) return null
    val values = listOf(info.appVersion, info.device, info.apiLevel.toString(), info.recent.joinToString(" > "))
    val query = entries.zip(values).joinToString("&") { (entry, value) -> "$entry=${encode(value)}" }
    return "$base?usp=pp_url&$query"
}

private fun encode(value: String) = URLEncoder.encode(value, "UTF-8").replace("+", "%20")
