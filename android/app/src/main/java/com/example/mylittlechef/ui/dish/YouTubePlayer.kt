// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.ui.dish

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Color
import android.util.Log
import android.os.Handler
import android.os.Looper
import android.webkit.ConsoleMessage
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceError
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
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
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.viewinterop.AndroidView
import com.example.mylittlechef.domain.DishLinks

/**
 * Plays one video through YouTube's own embedded player (IFrame API) in a page pinned to the full
 * WebView size. JavaScript is on for this WebView only, the player is shown unchanged at 16:9, any
 * navigation away from the page opens outside, and player errors are reported through [onError].
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun YouTubePlayer(videoId: String, modifier: Modifier = Modifier, onError: (String) -> Unit = {}) {
    val context = LocalContext.current
    val webView = remember(videoId) { createPlayerWebView(context, videoId, onError) }
    DisposableEffect(webView) {
        onDispose {
            webView.stopLoading()
            webView.loadUrl("about:blank")
            webView.destroy()
        }
    }
    AndroidView(
        factory = { webView },
        modifier = modifier.fillMaxWidth().aspectRatio(16f / 9f).semantics { contentDescription = "YouTube 영상 플레이어" }
    )
}

@SuppressLint("SetJavaScriptEnabled")
private fun createPlayerWebView(context: Context, videoId: String, onError: (String) -> Unit): WebView = WebView(context).apply {
    setBackgroundColor(Color.BLACK)
    settings.javaScriptEnabled = true
    settings.mediaPlaybackRequiresUserGesture = true
    val main = Handler(Looper.getMainLooper())
    addJavascriptInterface(object {
        @JavascriptInterface fun onError(code: String) { main.post { onError(code) } }
    }, DishLinks.PLAYER_BRIDGE)
    settings.allowFileAccess = false
    settings.allowContentAccess = false
    settings.cacheMode = WebSettings.LOAD_DEFAULT
    webChromeClient = object : WebChromeClient() {
        override fun onConsoleMessage(message: ConsoleMessage): Boolean {
            Log.d("DishPlayer", message.message())
            return true
        }
    }
    webViewClient = object : WebViewClient() {
        override fun onReceivedError(view: WebView, request: WebResourceRequest, error: WebResourceError) {
            Log.d("DishPlayer", "error ${error.errorCode} ${error.description} ${request.url}")
            if (request.isForMainFrame) main.post { onError("load ${error.errorCode}") }
        }

        override fun onReceivedHttpError(view: WebView, request: WebResourceRequest, errorResponse: WebResourceResponse) {
            Log.d("DishPlayer", "http ${errorResponse.statusCode} ${request.url}")
        }

        override fun shouldOverrideUrlLoading(view: WebView, request: WebResourceRequest): Boolean {
            val url = request.url.toString()
            // The embed itself and its assets stay inside; links out of the player go to the YouTube app or browser.
            if (request.isForMainFrame && url != DishLinks.EMBED_PAGE_URL) {
                openLink(view.context, url)
                return true
            }
            return false
        }
    }
    loadDataWithBaseURL(DishLinks.EMBED_PAGE_URL, DishLinks.playerHtml(videoId), "text/html", "utf-8", null)
}
