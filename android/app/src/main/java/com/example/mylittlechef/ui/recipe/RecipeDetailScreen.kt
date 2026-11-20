// Photo-led detail layout assisted by Codex, 2026-11-19; human review pending.
// HE selected-recipe state, consent, cancellation and cooking completion retained.
// Restored on the YouTube-based dishes with Claude Code (Opus 5.5), 2026-11-20: the photo slot plays
// the video the recipe was written from, the rows come from the stored recipe with what the fridge
// holds, "내 재료로 바꾸기" calls the server revision, and the other videos follow the steps.

package com.example.mylittlechef.ui.recipe

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.text
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil3.compose.AsyncImage
import com.example.mylittlechef.R
import com.example.mylittlechef.domain.Availability
import com.example.mylittlechef.domain.ChangeKind
import com.example.mylittlechef.domain.Dish
import com.example.mylittlechef.domain.DishLinks
import com.example.mylittlechef.domain.DishRecipe
import com.example.mylittlechef.domain.DishVideo
import com.example.mylittlechef.domain.RecipeChange
import com.example.mylittlechef.domain.Revision
import com.example.mylittlechef.ui.components.IngredientBadge
import com.example.mylittlechef.ui.dish.YouTubePlayer
import com.example.mylittlechef.ui.dish.openLink
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.RecipeUiState
import com.example.mylittlechef.viewmodel.ReviseUiState
import com.example.mylittlechef.viewmodel.VideoUiState
import kotlinx.coroutines.launch

/** One ingredient row as the detail shows it; [availability] is null in the revised recipe. */
data class RecipeRow(val name: String, val amount: String?, val availability: Availability?)

/** The chip next to a row: the #24 states plus "기본 양념" for what is assumed at home. */
internal fun availabilityLabel(availability: Availability): String = when (availability) {
    Availability.OWNED -> "준비됨"
    Availability.ASSUMED -> "기본 양념"
    Availability.UNAVAILABLE -> "부족"
}

/** Changes grouped as the old revision screen meant them: left out, used instead, the rest. */
internal fun changeGroups(changes: List<RecipeChange>): List<Pair<String, List<RecipeChange>>> = listOf(
    "뺀 재료" to changes.filter { it.kind == ChangeKind.OMISSION },
    "대신 쓴 재료" to changes.filter { it.kind == ChangeKind.SUBSTITUTION },
    "그 밖에 바뀐 점" to changes.filter { it.kind == ChangeKind.OTHER }
).filter { it.second.isNotEmpty() }

@Composable
fun RecipeDetailScreen(
    dish: Dish,
    liked: Boolean,
    recipe: RecipeUiState?,
    revision: ReviseUiState?,
    videos: VideoUiState?,
    fridge: FridgeViewModel?,
    onBackClick: () -> Unit,
    onLikeClick: () -> Unit,
    onRetryRecipe: () -> Unit,
    onRevise: () -> Unit,
    onRetryVideos: () -> Unit,
    onPlayerError: () -> Unit = {}
) {
    val stored = (recipe as? RecipeUiState.Success)?.recipe
    val revised = ((revision as? ReviseUiState.Done)?.revision as? Revision.Revised)
    var showSuggestion by rememberSaveable(dish.id) { mutableStateOf(false) }
    var showCompletion by rememberSaveable(dish.id) { mutableStateOf(false) }
    var picked by rememberSaveable(dish.id) { mutableStateOf<String?>(null) }
    val listed = (videos as? VideoUiState.Success)?.videos.orEmpty()
    val playingId = picked ?: stored?.videoId ?: listed.firstOrNull()?.videoId
    val showingRevised = showSuggestion && revised != null
    val rows = if (showingRevised) revised!!.ingredients.map { RecipeRow(it.name, it.amount, null) }
    else stored?.ingredients?.map { RecipeRow(it.name, it.amount, it.availability) }.orEmpty()
    val scope = rememberCoroutineScope(); val anchor = remember { BringIntoViewRequester() }
    val scroll = rememberScrollState()
    val pinned by remember { derivedStateOf { scroll.value > 180 } }
    val headerColor by animateColorAsState(if (pinned) MaterialTheme.colorScheme.background else Color.Transparent, tween(160), label = "detail-header")
    if (showCompletion && fridge != null && stored != null) CookingCompletionDialog(dish.id, stored, fridge) { showCompletion = false }
    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).statusBarsPadding().navigationBarsPadding()) {
        Column(Modifier.fillMaxSize().verticalScroll(scroll).testTag("recipe-detail-scroll")) {
            // The #24 photo slot: the video the recipe was written from (its still image until it is known).
            // The back and bookmark buttons sit in a band above the player so they never cover its controls.
            Box(Modifier.fillMaxWidth().heightIn(min = 236.dp).background(Color.Black).testTag("recipe-detail-photo"), contentAlignment = Alignment.Center) {
                if (playingId != null) {
                    var failed by remember(playingId) { mutableStateOf(false) }
                    if (failed) Text("이 영상은 앱에서 재생할 수 없어요. YouTube에서 열어 보세요.", Modifier.padding(24.dp),
                        color = Color.White, style = MaterialTheme.typography.bodyMedium)
                    else YouTubePlayer(playingId, Modifier.fillMaxWidth().padding(top = 52.dp), onError = { failed = true; onPlayerError() })
                } else RecipeImage(dish.name, dish.thumbnailUrl, Modifier.fillMaxWidth().height(236.dp))
            }
            Column(Modifier.fillMaxWidth().padding(20.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
                Text("오늘의 한 끼", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.primary)
                Text(dish.name, fontSize = 26.sp, fontWeight = FontWeight.SemiBold, lineHeight = 34.sp)
                if (stored != null) {
                    Text(credit(stored), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    if (playingId != null && stored.videoId != null && playingId != stored.videoId) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("아래 레시피는 ‘${stored.videoTitle ?: "레시피 영상"}’ 기준이에요.", Modifier.weight(1f),
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            TextButton(onClick = { picked = null }) { Text("레시피 영상 보기") }
                        }
                    }
                    val servings = (if (showingRevised) revised!!.servings else null) ?: stored.servings
                    servings?.let { Text(if (showingRevised) "제안 분량: ${it}인분" else "원본 분량: ${it}인분",
                        style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                }
                when (recipe) {
                    null, RecipeUiState.Loading -> Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        CircularProgressIndicator(Modifier.size(24.dp), color = MaterialTheme.colorScheme.primary)
                        Text("레시피를 불러오고 있어요…")
                    }
                    is RecipeUiState.Error -> Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(recipe.message, Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                        TextButton(onClick = onRetryRecipe, modifier = Modifier.testTag("recipe-retry")) { Text("다시 시도") }
                    }
                    is RecipeUiState.Success -> {
                        Box(Modifier.bringIntoViewRequester(anchor)) { RecipeIngredients(rows) }
                        Surface(color = MaterialTheme.colorScheme.surfaceVariant, shape = RoundedCornerShape(16.dp)) {
                            Box(Modifier.fillMaxWidth().padding(16.dp)) {
                                RevisionPanel(recipe.recipe, revision, showSuggestion,
                                    onRequest = { showSuggestion = true; onRevise() },
                                    onToggle = { showSuggestion = !showSuggestion },
                                    onOriginal = { showSuggestion = false; scope.launch { anchor.bringIntoView() } })
                            }
                        }
                        RecipeSteps(if (showingRevised) revised!!.steps.map { it.text } else recipe.recipe.steps.map { it.text })
                        val tips = if (showingRevised) revised!!.tips else recipe.recipe.tips
                        if (tips.isNotEmpty()) Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            tips.forEach { Text("· $it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                        }
                        if (fridge != null) {
                            Button(onClick = { showCompletion = true }, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp).testTag("recipe-complete"), shape = RoundedCornerShape(13.dp)) { Text("요리 완료") }
                            Text("다 쓴 재료만 골라 냉장고를 정리해요.", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }
                }
                OtherVideos(dish, videos, playingId, onRetryVideos) { picked = it }
                YouTubeCredit()
                Spacer(Modifier.height(24.dp))
            }
        }
        Row(Modifier.fillMaxWidth().background(headerColor).padding(horizontal = 12.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Surface(shape = RoundedCornerShape(24.dp), color = MaterialTheme.colorScheme.surface.copy(alpha = .94f)) {
                IconButton(onClick = onBackClick) { Icon(painterResource(R.drawable.ic_back), contentDescription = "back", modifier = Modifier.size(20.dp)) }
            }
            Box(Modifier.weight(1f).padding(horizontal = 12.dp)) {
                androidx.compose.animation.AnimatedVisibility(pinned, enter = fadeIn(tween(140)), exit = fadeOut(tween(100))) { Text(dish.name, style = MaterialTheme.typography.titleMedium, maxLines = 1) }
            }
            Surface(shape = RoundedCornerShape(24.dp), color = MaterialTheme.colorScheme.surface.copy(alpha = .94f)) {
                IconButton(onClick = onLikeClick, modifier = Modifier.testTag("recipe-detail-bookmark")) {
                    Icon(painterResource(if (liked) R.drawable.ic_ui_heart_filled else R.drawable.ic_ui_heart),
                        contentDescription = if (liked) "즐겨찾기 해제" else "즐겨찾기 추가", tint = MaterialTheme.colorScheme.primary, modifier = Modifier.size(22.dp))
                }
            }
        }
    }
}

private fun credit(recipe: DishRecipe): String {
    val video = listOfNotNull(recipe.videoChannel, recipe.videoTitle).joinToString(" · ")
    val origin = if (recipe.fromVideo) "AI가 영상을 보고 정리한 레시피" else "AI가 영상의 자막에서 정리한 레시피"
    return if (video.isBlank()) origin else "$origin · $video"
}

@Composable
fun RecipeIngredients(rows: List<RecipeRow>) {
    val missing = rows.count { it.availability == Availability.UNAVAILABLE }
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text("재료", Modifier.weight(1f), fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
            if (missing > 0) Text("부족한 재료 ${missing}개", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.height(10.dp))
        rows.forEach { row ->
            val short = row.availability == Availability.UNAVAILABLE
            val chip = row.availability?.let(::availabilityLabel)
            Row(Modifier.fillMaxWidth().heightIn(min = 54.dp).padding(vertical = 7.dp).testTag("recipe-ingredient-row-${row.name}"),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                IngredientBadge(row.name, size = 36.dp)
                val readable = row.name + row.amount?.takeIf { it.isNotBlank() }?.let { " $it" }.orEmpty() + chip?.let { " · $it" }.orEmpty()
                // Keep the name, amount and state readable as one accessible phrase.
                Row(Modifier.weight(1f).clearAndSetSemantics { text = AnnotatedString(readable) }, verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text(row.name, Modifier.weight(1f), fontSize = 14.sp, lineHeight = 20.sp)
                    row.amount?.takeIf { it.isNotBlank() }?.let { Text(it, Modifier.widthIn(max = 88.dp), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                    if (chip != null) Surface(color = if (short) MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.surfaceVariant, shape = RoundedCornerShape(6.dp)) {
                        Text(chip, Modifier.padding(horizontal = 6.dp, vertical = 4.dp), fontSize = 11.sp,
                            color = if (short) MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                }
            }
            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        }
    }
}

/** The #24 selected-revision panel on the server's revision: revised (toggle), refused or failed. */
@Composable
private fun RevisionPanel(recipe: DishRecipe, state: ReviseUiState?, showingSuggestion: Boolean,
    onRequest: () -> Unit, onToggle: () -> Unit, onOriginal: () -> Unit) {
    var changesExpanded by rememberSaveable(recipe.dishId) { mutableStateOf(false) }
    val revised = (state as? ReviseUiState.Done)?.revision as? Revision.Revised
    Column(Modifier.animateContentSize(tween(160)).testTag("revision-panel"), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(if (showingSuggestion && revised != null) "AI 수정 제안" else "원본 레시피", style = MaterialTheme.typography.titleMedium)
        Text("보유 재료를 고려해 이 요리의 재료와 조리법을 조정해요.", style = MaterialTheme.typography.bodyMedium)
        when {
            state == null -> if (recipe.hasMissing) Button(onClick = onRequest, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp).testTag("revise-button"),
                shape = RoundedCornerShape(13.dp)) { Text("내 재료로 바꾸기") }
            else Text("지금 재료로 그대로 만들 수 있어요.", color = MaterialTheme.colorScheme.primary)
            state is ReviseUiState.Loading -> Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                CircularProgressIndicator(Modifier.size(28.dp).testTag("selected-revision-progress"), color = MaterialTheme.colorScheme.primary)
                Text("이 요리의 제안을 만들고 있어요")
            }
            revised != null -> {
                OutlinedButton(onClick = onToggle, modifier = Modifier.heightIn(min = 48.dp).testTag("revision-toggle")) {
                    Text(if (showingSuggestion) "원본 보기" else "AI 제안 보기")
                }
                if (showingSuggestion) {
                    if (revised.changes.isEmpty()) Text("바꿀 것이 없어요. 지금 재료로 그대로 만들 수 있어요.")
                    else {
                        TextButton(onClick = { changesExpanded = !changesExpanded }, modifier = Modifier.testTag("revision-changes-toggle")) {
                            Text(if (changesExpanded) "변경 내용 접기" else "변경 내용 보기")
                        }
                        if (changesExpanded) changeGroups(revised.changes).forEach { (title, group) ->
                            Text(title, style = MaterialTheme.typography.labelLarge)
                            group.forEach { Text("• ${it.reason}", modifier = Modifier.testTag("recipe-change")) }
                        }
                    }
                    Text("AI 제안은 직접 확인해 주세요.", style = MaterialTheme.typography.bodySmall)
                }
            }
            else -> {
                val refused = (state as? ReviseUiState.Done)?.revision as? Revision.Refused
                val message = when (state) {
                    is ReviseUiState.Error -> state.message
                    is ReviseUiState.Done -> when (val r = state.revision) {
                        is Revision.Refused -> r.reason
                        is Revision.Failed -> r.message
                        else -> ""
                    }
                    else -> ""
                }
                if (refused != null) Text("지금 재료로는 바꾸기 어려워요", style = MaterialTheme.typography.titleSmall, modifier = Modifier.testTag("revise-refused"))
                Text(message.ifBlank { "조정하기 어려워요. 원본 레시피를 확인해 주세요." },
                    color = if (refused != null) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.error)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (refused == null) TextButton(onClick = onRequest, modifier = Modifier.testTag("revise-retry")) { Text("다시 시도") }
                    TextButton(onClick = onOriginal) { Text("원본 보기") }
                }
            }
        }
        Text("알레르기·조리도구 조건은 반영되지 않아요. 직접 확인해 주세요.", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable fun RecipeSteps(steps: List<String>) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(18.dp)) {
        Text("조리 방법", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
        steps.forEachIndexed { i, step ->
            val numberColor = MaterialTheme.colorScheme.primary
            Text(buildAnnotatedString {
                withStyle(SpanStyle(color = numberColor, fontWeight = FontWeight.SemiBold)) { append("${i + 1}. ") }
                append(step)
            }, Modifier.fillMaxWidth(), fontSize = 15.sp, lineHeight = 25.sp)
        }
    }
}

/** The dish's other videos in the detail's card style; picking one swaps the player at the top. */
@Composable
private fun OtherVideos(dish: Dish, videos: VideoUiState?, playingId: String?, onRetry: () -> Unit, onPlay: (String) -> Unit) {
    val context = LocalContext.current
    Column(Modifier.fillMaxWidth().testTag("recipe-other-videos"), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text("다른 영상", fontSize = 18.sp, fontWeight = FontWeight.SemiBold)
        when (videos) {
            null, VideoUiState.Loading -> Text("따라 하기 좋은 영상을 찾고 있어요…", style = MaterialTheme.typography.bodySmall)
            is VideoUiState.Error -> Row(verticalAlignment = Alignment.CenterVertically) {
                Text(videos.message, Modifier.weight(1f), style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.error)
                TextButton(onClick = onRetry) { Text("다시 시도") }
            }
            is VideoUiState.Success -> {
                if (videos.videos.isEmpty()) Text("이 요리의 영상을 찾지 못했어요.", style = MaterialTheme.typography.bodySmall)
                videos.videos.forEach { video -> VideoCard(video, video.videoId == playingId) { onPlay(video.videoId) } }
            }
        }
        TextButton(onClick = { openLink(context, dish.searchUrl) }) { Text("YouTube에서 더 검색", style = MaterialTheme.typography.labelMedium) }
    }
}

@Composable
private fun VideoCard(video: DishVideo, selected: Boolean, onPlay: () -> Unit) {
    Surface(Modifier.fillMaxWidth().clickable(role = Role.Button, onClickLabel = "영상 재생", onClick = onPlay), shape = RoundedCornerShape(13.dp),
        border = BorderStroke(1.dp, if (selected) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant),
        color = MaterialTheme.colorScheme.surface) {
        Row(Modifier.padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.width(120.dp).height(68.dp).clip(RoundedCornerShape(10.dp)).background(MaterialTheme.colorScheme.surfaceVariant)) {
                video.thumbnailUrl?.let { AsyncImage(model = it, contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize()) }
            }
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(video.title.ifBlank { "제목 없는 영상" }, style = MaterialTheme.typography.bodyMedium, maxLines = 2, overflow = TextOverflow.Ellipsis)
                Text(video.channel, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}

/** The YouTube credit and its two links (YouTube API terms); each link keeps a 48dp touch target. */
@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun YouTubeCredit() {
    val context = LocalContext.current
    val muted = MaterialTheme.colorScheme.onSurfaceVariant
    FlowRow(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        Text("Videos provided by YouTube ·", style = MaterialTheme.typography.labelSmall, color = muted,
            modifier = Modifier.heightIn(min = 48.dp).wrapContentHeight(Alignment.CenterVertically))
        listOf("서비스 약관" to DishLinks.TERMS_URL, "개인정보처리방침" to DishLinks.PRIVACY_URL).forEach { (label, url) ->
            Text(label, style = MaterialTheme.typography.labelSmall.copy(textDecoration = TextDecoration.Underline), color = muted,
                modifier = Modifier.heightIn(min = 48.dp).wrapContentHeight(Alignment.CenterVertically).clickable(role = Role.Button) { openLink(context, url) })
        }
    }
}
