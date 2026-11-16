// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.ui.dish

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import com.example.mylittlechef.domain.Dish
import com.example.mylittlechef.domain.DishLinks
import com.example.mylittlechef.domain.DishVideo

/** Videos for one dish: a vertical list; tapping an embeddable one plays it above the list. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DishVideoSheet(dish: Dish, onDismiss: () -> Unit) {
    val context = LocalContext.current
    var playingId by rememberSaveable(dish.id) { mutableStateOf<String?>(null) }
    val playing = dish.videos.firstOrNull { it.videoId == playingId }
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ) {
        Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 16.dp)) {
            Text(dish.name, style = MaterialTheme.typography.titleLarge)
            Spacer(Modifier.height(4.dp))
            Text(
                "이 요리를 만드는 YouTube 영상이에요. 영상은 올린 사람의 것이며 앱은 링크와 재생만 제공해요.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            Spacer(Modifier.height(12.dp))
            if (playing != null) {
                YouTubePlayer(playing.videoId)
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                    TextButton(onClick = { playingId = null }) { Text("재생 닫기") }
                    OutlinedButton(onClick = { openLink(context, DishLinks.watchUrl(playing.videoId)) }) {
                        Text("YouTube에서 열기")
                    }
                }
                Spacer(Modifier.height(8.dp))
            }
            if (dish.videos.isEmpty()) {
                Text("미리 찾아 둔 영상이 아직 없어요.", style = MaterialTheme.typography.bodyMedium)
                Spacer(Modifier.height(8.dp))
                OutlinedButton(onClick = { openLink(context, dish.searchUrl) }) { Text("YouTube에서 검색") }
            } else {
                LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    modifier = Modifier.weight(1f, fill = false)
                ) {
                    items(dish.videos, key = { it.videoId }) { video ->
                        VideoRow(
                            video = video,
                            selected = video.videoId == playingId,
                            onPlay = { playingId = video.videoId },
                            onOpen = { openLink(context, DishLinks.watchUrl(video.videoId)) }
                        )
                    }
                    item {
                        OutlinedButton(onClick = { openLink(context, dish.searchUrl) }) {
                            Text("YouTube에서 더 검색")
                        }
                    }
                }
            }
            Spacer(Modifier.height(12.dp))
            Attribution()
        }
    }
}

@Composable
private fun VideoRow(video: DishVideo, selected: Boolean, onPlay: () -> Unit, onOpen: () -> Unit) {
    val shape = RoundedCornerShape(12.dp)
    Row(
        Modifier
            .fillMaxWidth()
            .clip(shape)
            .background(
                if (selected) MaterialTheme.colorScheme.secondaryContainer
                else MaterialTheme.colorScheme.surfaceVariant
            )
            .clickable(onClickLabel = if (video.embeddable) "영상 재생" else "YouTube에서 열기") {
                if (video.embeddable) onPlay() else onOpen()
            }
            .padding(8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Box(
            Modifier.width(120.dp).height(68.dp).clip(RoundedCornerShape(8.dp))
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
        Column(Modifier.weight(1f).semantics { contentDescription = "${video.title}, ${video.channel}" }) {
            Text(
                video.title.ifBlank { "제목 없는 영상" },
                style = MaterialTheme.typography.bodyMedium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )
            Text(
                listOfNotNull(
                    video.channel.takeIf { it.isNotBlank() },
                    DishLinks.viewsLabel(video.viewCount)
                ).joinToString(" · "),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis
            )
            if (!video.embeddable) {
                Text(
                    "앱 안에서 재생할 수 없는 영상이에요",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
private fun Attribution() {
    val context = LocalContext.current
    Column {
        Text("Videos provided by YouTube", style = MaterialTheme.typography.labelMedium)
        Row {
            TextButton(onClick = { openLink(context, DishLinks.TERMS_URL) }) { Text("YouTube 서비스 약관") }
            TextButton(onClick = { openLink(context, DishLinks.PRIVACY_URL) }) { Text("Google 개인정보처리방침") }
        }
    }
}
