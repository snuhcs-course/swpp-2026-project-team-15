// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.ui.dish

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Color
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import com.example.mylittlechef.domain.DishLinks

/**
 * Plays one video through YouTube's own embedded player. JavaScript is on for this WebView only,
 * the player is shown unchanged at 16:9, and any navigation away from the embed opens outside.
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun YouTubePlayer(videoId: String, modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val webView = remember(videoId) { createPlayerWebView(context, videoId) }
    DisposableEffect(webView) {
        onDispose {
            webView.stopLoading()
            webView.loadUrl("about:blank")
            webView.destroy()
        }
    }
    AndroidView(
        factory = { webView },
        modifier = modifier.fillMaxWidth().aspectRatio(16f / 9f)
    )
}

@SuppressLint("SetJavaScriptEnabled")
private fun createPlayerWebView(context: Context, videoId: String): WebView = WebView(context).apply {
    setBackgroundColor(Color.BLACK)
    settings.javaScriptEnabled = true
    settings.mediaPlaybackRequiresUserGesture = true
    settings.allowFileAccess = false
    settings.allowContentAccess = false
    settings.cacheMode = WebSettings.LOAD_DEFAULT
    webViewClient = object : WebViewClient() {
        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            val url = request.url.toString()
            // The embed itself and its assets stay inside; links out of the player go to the YouTube app or browser.
            if (request.isForMainFrame && url != DishLinks.EMBED_BASE_URL && !url.startsWith("https://www.youtube.com/embed/")) {
                openLink(view.context, url)
                return true
            }
            return false
        }
    }
    loadDataWithBaseURL(DishLinks.EMBED_BASE_URL, DishLinks.embedHtml(videoId), "text/html", "utf-8", null)
}
