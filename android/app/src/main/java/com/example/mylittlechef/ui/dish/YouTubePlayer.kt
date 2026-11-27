// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
// Modified with Claude Code (Opus 5.5), 2026-11-20: the player is android-youtube-player's view.
// Modified with Claude Code (Opus 5.5), 2026-11-27: [onPlay] once per video when playback starts (usage data).
package com.example.mylittlechef.ui.dish

import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberUpdatedState
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.viewinterop.AndroidView
import com.example.mylittlechef.domain.DishLinks
import kotlinx.coroutines.delay
import java.util.concurrent.atomic.AtomicBoolean
import com.pierfrancescosoffritti.androidyoutubeplayer.core.player.PlayerConstants
import com.pierfrancescosoffritti.androidyoutubeplayer.core.player.YouTubePlayer as Player
import com.pierfrancescosoffritti.androidyoutubeplayer.core.player.listeners.AbstractYouTubePlayerListener
import com.pierfrancescosoffritti.androidyoutubeplayer.core.player.options.IFramePlayerOptions
import com.pierfrancescosoffritti.androidyoutubeplayer.core.player.views.YouTubePlayerView

/**
 * Plays one video through YouTube's own embedded player (IFrame API) with android-youtube-player,
 * shown unchanged at 16:9. The player identifies the app as the embedding origin (YouTube refuses
 * to play without a referrer of its own), and its errors are reported through [onError] with
 * YouTube's error name (e.g. VIDEO_NOT_FOUND, VIDEO_NOT_PLAYABLE_IN_EMBEDDED_PLAYER). [onPlay] is called the first
 * time the video actually plays: the video is only cued, so opening a recipe is not counted as a play.
 */
@Composable
fun YouTubePlayer(videoId: String, modifier: Modifier = Modifier, onError: (String) -> Unit = {}, onPlay: () -> Unit = {}) {
    val context = LocalContext.current
    val reportError by rememberUpdatedState(onError)
    val reportPlay by rememberUpdatedState(onPlay)
    // The library passes the id into a JavaScript call: only a well-formed YouTube id gets there.
    if (!DishLinks.isValidVideoId(videoId)) {
        LaunchedEffect(videoId) { reportError("INVALID_VIDEO_ID") }
        return
    }
    val ready = remember(videoId) { AtomicBoolean(false) }
    val played = remember(videoId) { AtomicBoolean(false) }
    // The library reports YouTube's errors but not a page that never loads (offline, blocked): without this the
    // player would just stay blank, where the earlier WebView showed the in-app notice on a load error.
    LaunchedEffect(videoId) { reportIfNotReady(ready::get, LOAD_TIMEOUT_MS) { reportError("LOAD_TIMEOUT") } }
    val view = remember(videoId) {
        YouTubePlayerView(context).apply {
            enableAutomaticInitialization = false
            val options = IFramePlayerOptions.Builder()
                .controls(1)
                .rel(0)
                .origin(DishLinks.EMBED_BASE_URL)
                .build()
            initialize(object : AbstractYouTubePlayerListener() {
                override fun onReady(youTubePlayer: Player) {
                    ready.set(true)
                    youTubePlayer.cueVideo(videoId, 0f)
                }
                override fun onError(youTubePlayer: Player, error: PlayerConstants.PlayerError) = reportError(error.name)
                override fun onStateChange(youTubePlayer: Player, state: PlayerConstants.PlayerState) {
                    if (firstPlay(state == PlayerConstants.PlayerState.PLAYING, played)) reportPlay()
                }
            }, options)
        }
    }
    DisposableEffect(view) { onDispose { view.release() } }
    AndroidView(
        factory = { view },
        modifier = modifier.fillMaxWidth().aspectRatio(16f / 9f).semantics { contentDescription = "YouTube 영상 플레이어" }
    )
}

/**
 * A judgement, not a measurement: long enough for the embed page on a slow mobile connection, short enough that
 * the notice with the "YouTube에서 열기" button comes before the user gives up on a blank box.
 */
const val LOAD_TIMEOUT_MS = 15_000L

/** Reports once when the player has not become ready within [timeoutMs]. */
suspend fun reportIfNotReady(isReady: () -> Boolean, timeoutMs: Long, report: () -> Unit) {
    delay(timeoutMs)
    if (!isReady()) report()
}

/** True only the first time [playing] holds for this video, so a pause and resume is not a second play. */
fun firstPlay(playing: Boolean, played: AtomicBoolean): Boolean = playing && played.compareAndSet(false, true)
