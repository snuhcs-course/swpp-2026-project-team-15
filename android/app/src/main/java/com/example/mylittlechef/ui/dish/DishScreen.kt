// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.ui.dish

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.VerticalDivider
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import com.example.mylittlechef.R
import com.example.mylittlechef.data.local.IngredientPresentationProvider
import com.example.mylittlechef.domain.Dish
import com.example.mylittlechef.domain.DishSort
import com.example.mylittlechef.ui.components.IngredientBadge
import com.example.mylittlechef.ui.fridge.components.ingredientIconResource
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.ui.theme.Gray
import com.example.mylittlechef.ui.theme.GreenGray
import com.example.mylittlechef.viewmodel.AdaptUiState
import com.example.mylittlechef.viewmodel.DishSheetMode
import com.example.mylittlechef.viewmodel.DishUiState
import com.example.mylittlechef.viewmodel.DishViewModel
import com.example.mylittlechef.viewmodel.VideoUiState
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.UserViewModel

/** Same card geometry as the recipe cards: a 96 dp square on the left, 24 dp corners, 16 dp list gaps. */
private val CardImageSize = 96.dp
private const val MaxBadges = 5

/** The recipe tab: dishes the fridge can make or nearly make, with videos and substitutions. */
@Composable
fun DishScreen(
    user: UserViewModel,
    fridge: FridgeViewModel,
    dishes: DishViewModel,
    modifier: Modifier = Modifier
) {
    val names = fridge.ingredients.map { it.name }
    var showInfo by remember { mutableStateOf(false) }
    LaunchedEffect(names) { dishes.onFridgeChanged(names) }

    Column(modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).padding(horizontal = 20.dp)) {
        Row(Modifier.fillMaxWidth().padding(top = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(
                "${user.nickname} 님의 요리",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onBackground,
                modifier = Modifier.weight(1f).semantics { heading() }
            )
            IconButton(
                onClick = { showInfo = true },
                modifier = Modifier.testTag("dish-info").semantics { contentDescription = "요리 추천 안내" }
            ) {
                Text("ⓘ", style = MaterialTheme.typography.headlineSmall, color = MaterialTheme.colorScheme.primary)
            }
        }
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Spacer(Modifier.weight(1f))
            DishSortDropdown(dishes.sort, dishes::selectSort)
        }
        when (val state = dishes.state) {
            DishUiState.EmptyFridge -> Message(
                "냉장고가 비어 있어요",
                "냉장고 탭에서 재료를 추가하면 만들 수 있는 요리와 영상을 추천해 드려요."
            )
            DishUiState.Loading -> Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    modifier = Modifier.semantics { liveRegion = LiveRegionMode.Polite }
                ) {
                    CircularProgressIndicator()
                    Spacer(Modifier.height(12.dp))
                    Text("요리를 찾고 있어요...", style = MaterialTheme.typography.bodyMedium)
                }
            }
            DishUiState.NoMatch -> Message(
                "지금 재료로 만들 수 있는 요리를 찾지 못했어요.",
                "재료를 더 넣어 보세요.",
                actionLabel = "다시 시도",
                onAction = dishes::retry
            )
            is DishUiState.Error -> Message(
                "요리를 불러오지 못했어요",
                state.message,
                actionLabel = "다시 시도",
                onAction = dishes::retry
            )
            is DishUiState.Success -> DishList(state, dishes)
        }
    }

    val selected = (dishes.state as? DishUiState.Success)?.dishes?.firstOrNull { it.id == dishes.selectedDishId }
    if (selected != null) {
        LaunchedEffect(selected.id) { dishes.requestVideos(selected) }
        DishDetailSheet(
            dish = selected,
            mode = dishes.selectedMode,
            fridgeNames = names,
            videos = dishes.videoState(selected.id),
            onLoadVideos = { dishes.requestVideos(selected) },
            adapt = dishes.adaptState(selected.id),
            onAdapt = { dishes.requestAdapt(selected) },
            onDismissAdapt = { dishes.dismissAdapt(selected.id) },
            onDismiss = { dishes.selectDish(null) }
        )
    }
    if (showInfo) {
        AlertDialog(
            onDismissRequest = { showInfo = false },
            title = { Text("요리 추천 안내") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("냉장고 재료 이름을 서버로 보내 만들 수 있는 요리를 골라요. 요리 목록은 서버가 정한 자취생 요리 안에서만 추천해요.")
                    Text("AI 대체 재료는 버튼을 눌렀을 때만 요청해요. 냉장고에 있는 재료만 쓰도록 제안하지만 맛과 알레르기는 직접 확인해 주세요.")
                    Text("영상은 YouTube에서 가져온 링크예요. 영상은 올린 사람의 것이에요.")
                }
            },
            confirmButton = { TextButton(onClick = { showInfo = false }) { Text("확인") } }
        )
    }
}

@Composable
private fun DishList(state: DishUiState.Success, dishes: DishViewModel) {
    LazyColumn(
        verticalArrangement = Arrangement.spacedBy(16.dp),
        modifier = Modifier.fillMaxSize().padding(horizontal = 8.dp).testTag("dish-list")
    ) {
        item { Spacer(Modifier.height(8.dp)) }
        items(state.dishes, key = { it.id }) { dish ->
            DishCard(
                dish,
                thumbnail = (dishes.videoState(dish.id) as? VideoUiState.Success)
                    ?.videos?.firstNotNullOfOrNull { it.thumbnailUrl },
                onOpen = { dishes.selectDish(dish.id, DishSheetMode.VIDEOS) },
                onAdapt = {
                    dishes.selectDish(dish.id, DishSheetMode.ADAPT)
                    if (dishes.adaptState(dish.id) == null) dishes.requestAdapt(dish)
                }
            )
        }
        item { Spacer(Modifier.height(24.dp)) }
    }
}

@Composable
private fun DishCard(dish: Dish, thumbnail: String?, onOpen: () -> Unit, onAdapt: () -> Unit) {
    // With very large text the card keeps its shape: the category and the action labels give way, long lines wrap.
    val large = LocalDensity.current.fontScale >= 1.3f
    val ingredients = remember(dish) { dish.have.map { it to true } + dish.missing.map { it to false } }
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(24.dp))
            .background(Gray)
            .testTag("dish-${dish.id}")
            .clickable(role = Role.Button, onClickLabel = "요리 상세 보기", onClick = onOpen)
    ) {
        Row(Modifier.fillMaxWidth().heightIn(min = CardImageSize), verticalAlignment = Alignment.CenterVertically) {
            DishThumbnail(dish, thumbnail, Modifier.size(CardImageSize).clip(RoundedCornerShape(24.dp)))
            Spacer(Modifier.weight(0.1f))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.Center) {
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        dish.name,
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                        maxLines = if (large) 2 else 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f, fill = false)
                    )
                    Spacer(Modifier.width(6.dp))
                    if (dish.category.isNotBlank() && !large) {
                        Text(
                            dish.category,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurface,
                            maxLines = 1
                        )
                    }
                }
                Spacer(Modifier.height(10.dp))
                if (dish.missing.isEmpty()) {
                    Text(
                        "지금 바로 만들 수 있어요",
                        style = MaterialTheme.typography.labelMedium,
                        color = DeepGreen,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                } else {
                    Text(
                        "${dish.missing.size}개 부족 · ${dish.missing.joinToString(", ")}",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                        maxLines = if (large) 2 else 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
                Spacer(Modifier.height(6.dp))
                BadgeRow(ingredients, dish)
            }
            Spacer(Modifier.weight(0.05f))
            VerticalDivider(thickness = 1.dp, color = GreenGray, modifier = Modifier.heightIn(min = CardImageSize))
            Column(
                Modifier.width(56.dp).heightIn(min = CardImageSize),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                CardAction(
                    R.drawable.ic_play,
                    "영상",
                    large,
                    "영상 보기",
                    Modifier.testTag("dish-videos-${dish.id}"),
                    onOpen
                )
                if (dish.missing.isNotEmpty()) {
                    CardAction(
                        R.drawable.ic_swap,
                        "대체",
                        large,
                        "AI 대체 재료 보기",
                        Modifier.testTag("dish-adapt-${dish.id}"),
                        onAdapt
                    )
                }
            }
        }
    }
}

/** One compact row of ingredient icons: the fridge's own in full colour, the missing ones faded and ringed. */
@Composable
private fun BadgeRow(ingredients: List<Pair<String, Boolean>>, dish: Dish) {
    val shown = ingredients.take(MaxBadges)
    val more = ingredients.size - shown.size
    val description = buildString {
        if (dish.have.isNotEmpty()) append("가진 재료: ${dish.have.joinToString(", ")}. ")
        if (dish.missing.isNotEmpty()) append("부족한 재료: ${dish.missing.joinToString(", ")}")
    }
    Row(
        Modifier.semantics(mergeDescendants = true) { contentDescription = description },
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        shown.forEach { (name, owned) ->
            if (owned) {
                IngredientBadge(name, size = 24.dp)
            } else {
                IngredientBadge(
                    name,
                    Modifier.alpha(0.4f).border(1.5.dp, MaterialTheme.colorScheme.error, CircleShape),
                    size = 24.dp
                )
            }
        }
        if (more > 0) Text("+$more", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurface)
    }
}

@Composable
private fun CardAction(
    icon: Int,
    label: String,
    hideLabel: Boolean,
    description: String,
    modifier: Modifier,
    onClick: () -> Unit
) {
    Column(
        modifier
            .heightIn(min = 48.dp)
            .width(56.dp)
            .clickable(role = Role.Button, onClick = onClick)
            .semantics { contentDescription = "$description, $label" },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center
    ) {
        Icon(painterResource(icon), contentDescription = null, tint = MaterialTheme.colorScheme.onSurface, modifier = Modifier.size(22.dp))
        if (!hideLabel) {
            Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurface, maxLines = 1)
        }
    }
}

/** The first video's thumbnail once the videos were loaded; until then the ingredient icon tile every other screen uses. */
@Composable
private fun DishThumbnail(dish: Dish, thumbnail: String?, modifier: Modifier) {
    val context = LocalContext.current
    val first = (dish.have + dish.missing).firstOrNull()
    val appearance = remember(first) { first?.let { IngredientPresentationProvider.get(context).appearanceFor(it) } }
    Box(
        modifier.background(appearance?.let { Color(it.backgroundArgb) } ?: MaterialTheme.colorScheme.outlineVariant),
        contentAlignment = Alignment.Center
    ) {
        if (appearance != null) {
            Icon(
                painterResource(ingredientIconResource(appearance.iconKey)),
                contentDescription = null,
                tint = Color(0xFF172C25),
                modifier = Modifier.size(64.dp)
            )
        }
        if (thumbnail != null) {
            AsyncImage(
                model = thumbnail,
                contentDescription = null,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize()
            )
        }
    }
}

@Composable
private fun Message(title: String, body: String, actionLabel: String? = null, onAction: () -> Unit = {}) {
    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.padding(24.dp)) {
            Text(title, style = MaterialTheme.typography.titleMedium, modifier = Modifier.semantics { heading() })
            Spacer(Modifier.height(8.dp))
            Text(body, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (actionLabel != null) {
                Spacer(Modifier.height(16.dp))
                Button(onClick = onAction, modifier = Modifier.testTag("dish-retry")) { Text(actionLabel) }
            }
        }
    }
}

@Composable
private fun DishSortDropdown(selected: DishSort, onSelected: (DishSort) -> Unit) {
    var expanded by remember { mutableStateOf(false) }
    Box {
        OutlinedButton(
            onClick = { expanded = true },
            border = BorderStroke(1.dp, MaterialTheme.colorScheme.outline),
            modifier = Modifier.testTag("dish-sort-trigger").semantics {
                contentDescription = "정렬 기준 선택"
                stateDescription = selected.label
            }
        ) {
            Text(
                "정렬: ${selected.label} ⌄",
                maxLines = if (LocalDensity.current.fontScale >= 1.3f) 2 else 1,
                modifier = Modifier.clearAndSetSemantics { }
            )
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            DishSort.entries.forEach { type ->
                DropdownMenuItem(text = { Text(type.label) }, onClick = { onSelected(type); expanded = false })
            }
        }
    }
}
