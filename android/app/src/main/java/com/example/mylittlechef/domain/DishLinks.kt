// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.domain

import java.net.URI
import java.net.URLEncoder

/** Pure URL and text helpers for the YouTube parts; no Android types so they are unit-testable. */
object DishLinks {
    const val TERMS_URL = "https://www.youtube.com/t/terms"
    const val PRIVACY_URL = "https://policies.google.com/privacy"
    /** Identifies the app to YouTube as the embedding client (the player refuses to load without a referrer of its own). */
    const val EMBED_BASE_URL = "https://com.example.mylittlechef"

    private val VIDEO_ID = Regex("^[A-Za-z0-9_-]{11}$")

    fun isValidVideoId(id: String) = VIDEO_ID.matches(id)

    fun watchUrl(videoId: String) = "https://www.youtube.com/watch?v=$videoId"

    fun embedUrl(videoId: String) = "https://www.youtube.com/embed/$videoId?playsinline=1&rel=0"

    fun searchUrl(query: String) =
        "https://www.youtube.com/results?search_query=" + URLEncoder.encode(query, "UTF-8")

    /** Uses the server's link only when it points at youtube.com over https; otherwise builds one. */
    fun safeSearchUrl(candidate: String?, fallbackQuery: String): String {
        val host = runCatching { URI(candidate ?: "").let { if (it.scheme == "https") it.host else null } }.getOrNull()
        val ok = host != null && (host == "youtube.com" || host.endsWith(".youtube.com"))
        return if (ok) candidate!! else searchUrl("$fallbackQuery 레시피")
    }
}
