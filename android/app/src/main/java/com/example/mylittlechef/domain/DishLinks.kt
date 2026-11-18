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
    const val EMBED_PAGE_URL = "$EMBED_BASE_URL/"

    private val VIDEO_ID = Regex("^[A-Za-z0-9_-]{11}$")

    fun isValidVideoId(id: String) = VIDEO_ID.matches(id)

    fun watchUrl(videoId: String) = "https://www.youtube.com/watch?v=$videoId"

    fun embedUrl(videoId: String) = "https://www.youtube.com/embed/$videoId?playsinline=1&rel=0"

    /** Name of the JavaScript bridge the player page calls with YouTube's error code. */
    const val PLAYER_BRIDGE = "MlcPlayer"

    /**
     * Page that hosts YouTube's iframe player at a fixed full size. Loading `/embed/ID` as the top-level
     * page left its body at height 0, so the video (audio played) had no height and nothing was drawn;
     * here the player div is pinned to the whole WebView. [onError] receives the IFrame API error code
     * (100 not found or private, 101/150 embedding disabled, 153 missing referrer).
     */
    fun playerHtml(videoId: String): String {
        require(isValidVideoId(videoId)) { "invalid video id" }
        return """<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<style>html,body,#p{margin:0;width:100%;height:100%;background:#000}#p{position:fixed;left:0;top:0}</style></head>
<body><div id="p"></div><script>
function onYouTubeIframeAPIReady(){new YT.Player('p',{width:'100%',height:'100%',videoId:'$videoId',
playerVars:{playsinline:1,rel:0,origin:'$EMBED_BASE_URL'},events:{onError:function(e){$PLAYER_BRIDGE.onError(String(e.data))}}})}
var t=document.createElement('script');t.src='https://www.youtube.com/iframe_api';document.head.appendChild(t);
</script></body></html>"""
    }

    fun searchUrl(query: String) =
        "https://www.youtube.com/results?search_query=" + URLEncoder.encode(query, "UTF-8")

    /** Uses the server's link only when it points at youtube.com over https; otherwise builds one. */
    fun safeSearchUrl(candidate: String?, fallbackQuery: String): String {
        val host = runCatching { URI(candidate ?: "").let { if (it.scheme == "https") it.host else null } }.getOrNull()
        val ok = host != null && (host == "youtube.com" || host.endsWith(".youtube.com"))
        return if (ok) candidate!! else searchUrl("$fallbackQuery 레시피")
    }
}
