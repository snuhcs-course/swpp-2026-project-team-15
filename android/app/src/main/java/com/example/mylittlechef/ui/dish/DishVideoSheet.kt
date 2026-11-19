// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.ui.dish

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.wrapContentHeight
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import com.example.mylittlechef.domain.Dish
import com.example.mylittlechef.domain.DishLinks
import com.example.mylittlechef.domain.DishVideo
import com.example.mylittlechef.ui.components.IngredientBadge
import com.example.mylittlechef.viewmodel.RecipeUiState
import com.example.mylittlechef.viewmodel.ReviseUiState
import com.example.mylittlechef.viewmodel.VideoUiState

/**
 * One dish on one screen. With a stored recipe: the video the recipe was written from plays first,
 * the recipe follows, then the other videos (picking one only swaps the player). Without a recipe:
 * the videos. Substitutions now come from "내 재료로 바꾸기" inside the recipe (2026-11-19).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DishDetailSheet(
    dish: Dish,
    videos: VideoUiState?,
    onLoadVideos: () -> Unit,
    recipe: RecipeUiState?,
    revision: ReviseUiState?,
    onRetryRecipe: () -> Unit,
    onRevise: () -> Unit,
    onDismiss: () -> Unit
) {
    val stored = (recipe as? RecipeUiState.Success)?.recipe
    val listed = (videos as? VideoUiState.Success)?.videos.orEmpty()
    var picked by rememberSaveable(dish.id) { mutableStateOf<String?>(null) }
    val playingId = picked ?: stored?.videoId
    val playing = listed.firstOrNull { it.videoId == playingId }
        ?: playingId?.let { DishVideo(it, stored?.videoTitle.orEmpty(), stored?.videoChannel.orEmpty(), null) }
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ) {
        Column(
            Modifier.verticalScroll(rememberScrollState()).padding(horizontal = 20.dp).padding(bottom = 16.dp)
                .testTag("dish-sheet")
        ) {
            Text(dish.name, style = MaterialTheme.typography.titleLarge, modifier = Modifier.semantics { heading() })
            if (dish.reason.isNotBlank()) {
                Spacer(Modifier.height(4.dp))
                Text(dish.reason, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.height(12.dp))
            if (playing != null) {
                Player(playing, onClose = if (dish.hasRecipe) null else ({ picked = null }))
                if (stored != null && playing.videoId != stored.videoId) {
                    val title = stored.videoTitle ?: "다른 영상"
                    Text(
                        "아래 레시피는 ‘$title’ 영상 기준이에요.",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    TextButton(onClick = { picked = null }) { Text("레시피 영상으로 돌아가기") }
                }
                Spacer(Modifier.height(12.dp))
            }
            if (dish.hasRecipe) {
                RecipeSection(recipe, revision, onRetryRecipe, onRevise)
                Spacer(Modifier.height(20.dp))
            }
            VideoSection(
                dish,
                videos,
                onLoadVideos,
                title = if (dish.hasRecipe) "다른 영상" else "영상",
                playingId = playing?.videoId,
                onPlay = { picked = it }
            )
            Spacer(Modifier.height(4.dp))
            Attribution()
        }
    }
}

/** The in-app player with its fallback notice and a link to YouTube; [onClose] is null when the player stays. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Player(video: DishVideo, onClose: (() -> Unit)?) {
    val context = LocalContext.current
    var failed by remember(video.videoId) { mutableStateOf(false) }
    if (failed) {
        Text(
            "이 영상은 앱에서 재생할 수 없어요. YouTube에서 열어 보세요.",
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }
        )
    } else {
        Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
            YouTubePlayer(video.videoId, Modifier.widthIn(max = 480.dp), onError = { failed = true })
        }
    }
    FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
        if (onClose != null) TextButton(onClick = onClose) { Text("재생 닫기") }
        OutlinedButton(onClick = { openLink(context, DishLinks.watchUrl(video.videoId)) }) {
            Text("YouTube에서 열기")
        }
    }
}

@Composable
private fun VideoSection(
    dish: Dish,
    videos: VideoUiState?,
    onRetry: () -> Unit,
    title: String,
    playingId: String?,
    onPlay: (String) -> Unit
) {
    val context = LocalContext.current
    Text(title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.semantics { heading() })
    Spacer(Modifier.height(8.dp))
    when (videos) {
        null, VideoUiState.Loading -> Row(
            Modifier.semantics { liveRegion = LiveRegionMode.Polite },
            verticalAlignment = Alignment.CenterVertically
        ) {
            CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
            Spacer(Modifier.width(8.dp))
            Text("따라 하기 좋은 영상을 찾고 있어요...", style = MaterialTheme.typography.bodyMedium)
        }
        is VideoUiState.Error -> Column(Modifier.semantics { liveRegion = LiveRegionMode.Polite }) {
            Text(videos.message, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.error)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onRetry) { Text("다시 시도") }
                TextButton(onClick = { openLink(context, dish.searchUrl) }) { Text("YouTube에서 검색", style = MaterialTheme.typography.labelMedium) }
            }
        }
        is VideoUiState.Success -> if (videos.videos.isEmpty()) {
            Text("이 요리의 영상을 찾지 못했어요.", style = MaterialTheme.typography.bodyMedium)
            Spacer(Modifier.height(8.dp))
            TextButton(onClick = { openLink(context, dish.searchUrl) }) { Text("YouTube에서 검색", style = MaterialTheme.typography.labelMedium) }
        } else {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                videos.videos.forEach { video ->
                    VideoRow(
                        video = video,
                        selected = video.videoId == playingId,
                        onPlay = { onPlay(video.videoId) }
                    )
                }
                TextButton(onClick = { openLink(context, dish.searchUrl) }) { Text("YouTube에서 더 검색", style = MaterialTheme.typography.labelMedium) }
            }
        }
    }
}

/** Fixed-size row: 16:9 thumbnail, two-line title, one line for the channel. */
@Composable
private fun VideoRow(video: DishVideo, selected: Boolean, onPlay: () -> Unit) {
    val shape = RoundedCornerShape(24.dp)
    Row(
        Modifier
            .fillMaxWidth()
            .clip(shape)
            .background(
                if (selected) MaterialTheme.colorScheme.secondaryContainer
                else MaterialTheme.colorScheme.surfaceVariant
            )
            .semantics(mergeDescendants = true) {
                contentDescription = listOfNotNull(
                    video.title.ifBlank { "제목 없는 영상" },
                    video.channel.takeIf { it.isNotBlank() }
                ).joinToString(", ")
            }
            .clickable(onClickLabel = "영상 재생", role = Role.Button, onClick = onPlay)
            .padding(8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            Modifier.width(120.dp).height(68.dp).clip(RoundedCornerShape(16.dp))
                .background(MaterialTheme.colorScheme.outline)
        ) {
            if (video.thumbnailUrl != null) {
                AsyncImage(
                    model = video.thumbnailUrl,
                    contentDescription = null,
                    contentScale = ContentScale.Crop,
                    modifier = Modifier.size(width = 120.dp, height = 68.dp)
                )
            }
        }
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f).height(68.dp), verticalArrangement = Arrangement.Center) {
            Text(
                video.title.ifBlank { "제목 없는 영상" },
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )
            Text(
                video.channel,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
        }
    }
}

/** One muted caption row: the required YouTube credit and its two links; each link keeps a 48dp touch target. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Attribution() {
    val context = LocalContext.current
    val caption = MaterialTheme.typography.labelSmall
    val muted = MaterialTheme.colorScheme.onSurfaceVariant
    FlowRow(
        Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalArrangement = Arrangement.Center
    ) {
        Text(
            "Videos provided by YouTube ·",
            style = caption,
            color = muted,
            modifier = Modifier.heightIn(min = 48.dp).wrapContentHeight(Alignment.CenterVertically)
        )
        CaptionLink("서비스 약관", "YouTube 서비스 약관") { openLink(context, DishLinks.TERMS_URL) }
        Text("·", style = caption, color = muted, modifier = Modifier.heightIn(min = 48.dp).wrapContentHeight(Alignment.CenterVertically))
        CaptionLink("개인정보처리방침", "Google 개인정보처리방침") { openLink(context, DishLinks.PRIVACY_URL) }
    }
}

@Composable
private fun CaptionLink(label: String, description: String, onClick: () -> Unit) {
    Text(
        label,
        style = MaterialTheme.typography.labelSmall.copy(textDecoration = TextDecoration.Underline),
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier
            .heightIn(min = 48.dp)
            .wrapContentHeight(Alignment.CenterVertically)
            .semantics { contentDescription = description }
            .clickable(role = Role.Button, onClick = onClick)
    )
}
