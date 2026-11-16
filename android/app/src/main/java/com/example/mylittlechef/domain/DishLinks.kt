// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.domain

import java.net.URI
import java.net.URLEncoder

/** Pure URL and text helpers for the YouTube parts; no Android types so they are unit-testable. */
object DishLinks {
    const val TERMS_URL = "https://www.youtube.com/t/terms"
    const val PRIVACY_URL = "https://policies.google.com/privacy"
    const val EMBED_BASE_URL = "https://www.youtube.com"

    private val VIDEO_ID = Regex("^[A-Za-z0-9_-]{11}$")

    fun isValidVideoId(id: String) = VIDEO_ID.matches(id)

    fun watchUrl(videoId: String) = "https://www.youtube.com/watch?v=$videoId"

    fun embedUrl(videoId: String) = "https://www.youtube.com/embed/$videoId?playsinline=1&rel=0"

    /** Page for loadDataWithBaseURL: only the player iframe, nothing drawn over it. */
    fun embedHtml(videoId: String): String =
        "<!DOCTYPE html><html><head><meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">" +
            "<style>html,body{margin:0;padding:0;background:#000;height:100%}" +
            "iframe{border:0;width:100%;height:100%}</style></head><body>" +
            "<iframe src=\"${embedUrl(videoId)}\" title=\"YouTube video player\" " +
            "allow=\"accelerometer; encrypted-media; gyroscope; picture-in-picture\" allowfullscreen></iframe>" +
            "</body></html>"

    fun searchUrl(query: String) =
        "https://www.youtube.com/results?search_query=" + URLEncoder.encode(query, "UTF-8")

    /** Uses the server's link only when it points at youtube.com over https; otherwise builds one. */
    fun safeSearchUrl(candidate: String?, fallbackQuery: String): String {
        val host = runCatching { URI(candidate ?: "").let { if (it.scheme == "https") it.host else null } }.getOrNull()
        val ok = host != null && (host == "youtube.com" || host.endsWith(".youtube.com"))
        return if (ok) candidate!! else searchUrl("$fallbackQuery 레시피")
    }

    /** 12345 -> "1.2만회", 999 -> "999회"; unknown counts are hidden. */
    fun viewsLabel(count: Long?): String? = when {
        count == null || count < 0 -> null
        count >= 100_000_000 -> "조회수 %.1f억회".format(count / 100_000_000.0)
        count >= 10_000 -> "조회수 %.1f만회".format(count / 10_000.0)
        else -> "조회수 ${count}회"
    }
}
