// UAT stage 4 assisted by Codex, 2026-11-24; human review pending.
// UAT stage 3 assisted by Codex, 2026-11-24; human review pending.
// Photo-led list and stable scrolling assisted by Codex, 2026-11-19; human review pending.
// HE ingredient/exploration changes assisted by Codex, 2026-11-10; human review pending.
// UI ergonomics and theme changes assisted by Codex, 2026-11-03; human review pending.
// Restored on the YouTube-based dishes with Claude Code (Opus 5.5), 2026-11-20: the list shows the
// server's suggested dishes; search filters received candidates and bookmarks stay on the phone.
// Pull-to-refresh rotates the visible candidate batch. Full-catalogue search, cooking-time labels
// and the batch AI tab still require separate server/data support.

package com.example.mylittlechef.ui.recipe

import com.example.mylittlechef.ui.components.IngredientLoading
import com.example.mylittlechef.ui.components.LoadingTask
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import kotlinx.coroutines.awaitCancellation
import com.example.mylittlechef.ui.help.LocalSectionTour
import com.example.mylittlechef.ui.help.tourAnchor
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.*
import androidx.compose.material3.pulltorefresh.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalSoftwareKeyboardController
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.mylittlechef.R
import com.example.mylittlechef.domain.Dish
import com.example.mylittlechef.viewmodel.DishUiState
import com.example.mylittlechef.viewmodel.DishViewModel
import com.example.mylittlechef.viewmodel.FridgeViewModel

enum class RecipeTab { RECOMMENDED, LIKE }

@Composable
fun RecipeScreen(fridge: FridgeViewModel, dishes: DishViewModel, onDishClick: (Dish) -> Unit, modifier: Modifier = Modifier, active:Boolean=true) {
    val names = fridge.ingredients.map { it.name }
    val tourActive=LocalSectionTour.current?.active == true
    val owner=LocalLifecycleOwner.current
    LaunchedEffect(names,tourActive,owner,active) {
        if(active && !tourActive) owner.lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            dishes.onFridgeChanged(names)
            awaitCancellation()
        }
    }
    RecipeContent(dishes, onDishClick, modifier)
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun RecipeContent(dishes: DishViewModel, onDishClick: (Dish) -> Unit, modifier: Modifier = Modifier) {
    var selectedTab by rememberSaveable { mutableStateOf(RecipeTab.RECOMMENDED) }
    var showInfo by remember { mutableStateOf(false) }
    var searchText by rememberSaveable { mutableStateOf("") }
    var query by rememberSaveable { mutableStateOf("") }
    val keyboard=LocalSoftwareKeyboardController.current
    val search={ keyboard?.hide(); query=searchText }
    val snackbar=remember {SnackbarHostState()}
    val pullState=rememberPullToRefreshState()
    val feedback=dishes.refreshFeedback
    LaunchedEffect(feedback) {
        feedback?.let {
            snackbar.showSnackbar(if(query.isNotBlank()) "추천을 다시 불러왔어요." else if(it.changed) "다른 추천을 준비했어요." else "새로 받은 추천이 이전과 같아요.")
            dishes.consumeRefreshFeedback(it.id)
        }
    }
    val state=dishes.state
    val loading=state is DishUiState.Loading
    val error=(state as? DishUiState.Error)?.message
    val visible=when(selectedTab) {
        RecipeTab.RECOMMENDED -> dishes.visibleSuggestions(query)
        RecipeTab.LIKE -> dishes.favoriteDishes()
    }
    Box(modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
        Column(Modifier.fillMaxSize()) {
            Row(Modifier.fillMaxWidth().padding(start=20.dp,end=12.dp,top=12.dp,bottom=8.dp),verticalAlignment=Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("오늘의 레시피",style=MaterialTheme.typography.titleLarge,fontSize=22.sp)
                    Text("우리 집 재료에서 시작하는 한 끼",style=MaterialTheme.typography.bodySmall,
                        color=MaterialTheme.colorScheme.onSurfaceVariant,modifier=Modifier.padding(top=5.dp))
                }
                IconButton(onClick={showInfo=true},modifier=Modifier.testTag("recipe-info").semantics { contentDescription="레시피 안내" }) {
                    Icon(painterResource(R.drawable.ic_ui_info),contentDescription=null,modifier=Modifier.size(22.dp))
                }
            }
            if(selectedTab==RecipeTab.RECOMMENDED) {
                OutlinedTextField(searchText,{searchText=it.take(100); if(it.isBlank()) query=""},singleLine=true,
                    placeholder={Text("레시피 이름 검색",style=MaterialTheme.typography.bodyMedium)},
                    leadingIcon={Icon(painterResource(R.drawable.ic_ui_search),contentDescription=null,modifier=Modifier.size(20.dp))},
                    trailingIcon={IconButton(onClick={search()},modifier=Modifier.testTag("recipe-search-submit")) {
                        Text("검색",style=MaterialTheme.typography.labelMedium,color=MaterialTheme.colorScheme.primary)
                    }},shape=RoundedCornerShape(13.dp),
                    modifier=Modifier.fillMaxWidth().padding(horizontal=20.dp).testTag("recipe-search").tourAnchor("recipe-browse"),
                    colors=OutlinedTextFieldDefaults.colors(unfocusedContainerColor=MaterialTheme.colorScheme.surfaceVariant,
                        unfocusedBorderColor=MaterialTheme.colorScheme.outlineVariant),
                    keyboardOptions=KeyboardOptions(imeAction=ImeAction.Search),keyboardActions=KeyboardActions(onSearch={search()}))
            }
            Row(Modifier.fillMaxWidth().padding(horizontal=12.dp).horizontalScroll(rememberScrollState())) {
                listOf(RecipeTab.RECOMMENDED to "추천",RecipeTab.LIKE to "즐겨찾기").forEach { (tab,label) ->
                    Column(horizontalAlignment=Alignment.CenterHorizontally) {
                        TextButton(onClick={selectedTab=tab},modifier=Modifier.testTag("recipe-tab-${tab.name}")) { Text(label,style=MaterialTheme.typography.labelMedium,
                            color=if(selectedTab==tab) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant) }
                        HorizontalDivider(Modifier.width(if(tab==RecipeTab.LIKE) 64.dp else 48.dp),thickness=2.dp,
                            color=if(selectedTab==tab) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.background)
                    }
                }
            }
            Row(Modifier.fillMaxWidth().padding(horizontal=20.dp),verticalAlignment=Alignment.CenterVertically) {
                Spacer(Modifier.weight(1f)); RecipeSortDropdown(dishes.sort,dishes::selectSort)
            }
            if(selectedTab==RecipeTab.RECOMMENDED && !loading && dishes.showingPreviousSuggestions)
                Text("이전 목록이에요. 새 조회 결과가 도착하면 바뀌어요.",Modifier.padding(horizontal=20.dp),
                    style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
            error?.let { message -> Row(Modifier.padding(horizontal=20.dp),verticalAlignment=Alignment.CenterVertically) {
                Text(message,Modifier.weight(1f),style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.error)
                TextButton(onClick=dishes::retry) {Text("다시 시도")}
            } }
            if(selectedTab==RecipeTab.RECOMMENDED) {
                if(query.isNotBlank()) Text("불러온 목록에서 검색해요.",Modifier.padding(horizontal=20.dp),style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                if(!loading && dishes.lastHidden!=null) Row(Modifier.padding(horizontal=20.dp),verticalAlignment=Alignment.CenterVertically) {
                    Text("이번 목록에서 숨겼어요.",Modifier.weight(1f),style=MaterialTheme.typography.bodySmall)
                    TextButton(onClick=dishes::undoHide) {Text("실행 취소")}
                }
            }
            Box(Modifier.weight(1f).fillMaxWidth().testTag("recipe-list-content")) {
                val results:@Composable BoxScope.()->Unit = {
                    if(selectedTab==RecipeTab.RECOMMENDED && loading) {
                        Box(Modifier.fillMaxSize(),contentAlignment=Alignment.Center) {
                            IngredientLoading(LoadingTask.DISHES,
                                Modifier.padding(16.dp).testTag("recipe-list-progress"))
                        }
                    } else if(error==null&&visible.isEmpty()) {
                        Box(Modifier.fillMaxSize().verticalScroll(rememberScrollState()),contentAlignment=Alignment.Center) {
                            Text(when {
                                selectedTab==RecipeTab.LIKE -> "즐겨찾기한 레시피가 없어요."
                                state is DishUiState.EmptyFridge -> "냉장고에 재료를 넣으면 만들 수 있는 요리를 보여 드려요."
                                state is DishUiState.NoMatch -> "지금 재료로 만들 수 있는 요리를 찾지 못했어요."
                                else -> "검색 조건에 맞는 레시피가 없어요."
                            },Modifier.padding(24.dp).testTag("recipe-empty"),color=MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    } else {
                        RecipeCardList(dishes,visible,onDishClick,
                            if(selectedTab==RecipeTab.RECOMMENDED) ({dishes.hide(it.id)}) else null,
                            refreshVersion=if(selectedTab==RecipeTab.RECOMMENDED) dishes.refreshVersion else 0L)

                    }
                }
                if(selectedTab==RecipeTab.RECOMMENDED) {
                    PullToRefreshBox(isRefreshing=loading,onRefresh=dishes::refreshSuggestions,state=pullState,
                        modifier=Modifier.fillMaxSize().testTag("recipe-pull-refresh"),
                        indicator={if(!loading) PullToRefreshDefaults.Indicator(
                            state=pullState,isRefreshing=false,modifier=Modifier.align(Alignment.TopCenter))},
                        content=results)
                } else Box(Modifier.fillMaxSize(),content=results)
            }
        }
        SnackbarHost(snackbar,Modifier.align(Alignment.BottomCenter).padding(16.dp))
    }
    if(showInfo) AlertDialog(onDismissRequest={showInfo=false},title={Text("레시피 안내")},text={Column(Modifier.verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(12.dp)) {
        Text("냉장고 재료로 만들 수 있는 요리를 골랐어요. 카드의 부족한 재료는 요리의 핵심 재료 기준이에요.")
        Text("카드를 누르면 레시피를 만든 영상과 레시피가 함께 나와요. ‘내 재료로 바꾸기’를 누르면 AI가 레시피를 내 재료에 맞게 고쳐요. 원본은 그대로 남아요.")
        Text("목록 맨 위에서 아래로 당기면 다른 추천을 받아요. 새 후보가 없으면 같은 요리가 나올 수 있어요.")
        Text("재료와 조리법을 직접 확인한 뒤 조리해 주세요.")
        Text("영상은 YouTube에서 가져온 링크예요. 영상은 올린 사람의 것이에요.")
    }},confirmButton={TextButton(onClick={showInfo=false}) {Text("확인")}})
}

@Composable
fun RecipeCardList(dishes:DishViewModel,items:List<Dish>,onDishClick:(Dish)->Unit,onHide:((Dish)->Unit)?=null,refreshVersion:Long=0L) {
    val listState=rememberLazyListState()
    LaunchedEffect(refreshVersion) {if(refreshVersion>0 && items.isNotEmpty()) listState.scrollToItem(0)}
    // After "실행 취소" the card returns where it was, often above the visible part of the list:
    // scroll to it so the user sees it come back (emulator E2E, 2026-11-20).
    val restored=dishes.restored
    LaunchedEffect(restored) {
        val index=restored?.let { r -> items.indexOfFirst { it.id==r.id } } ?: -1
        if(index>=0) listState.animateScrollToItem(index)
    }
    LazyColumn(state=listState,contentPadding=PaddingValues(start=20.dp,end=20.dp,top=10.dp,bottom=88.dp),
        verticalArrangement=Arrangement.spacedBy(18.dp),modifier=Modifier.fillMaxSize().testTag("recipe-list")) {
        items(items,key={it.id}) {dish ->
            Box(Modifier.animateItem(fadeInSpec=tween(160),fadeOutSpec=tween(100))) {
                if(onHide!=null) {
                    val dismiss=rememberSwipeToDismissBoxState(confirmValueChange={value->if(value==SwipeToDismissBoxValue.EndToStart){onHide(dish);true}else false})
                    // The swipe state is saved per dish: after "실행 취소" the card comes back swiped away
                    // unless it is reset when it re-enters the list (found on the emulator, 2026-11-20).
                    LaunchedEffect(dish.id) { if(dismiss.currentValue!=SwipeToDismissBoxValue.Settled) dismiss.reset() }
                    SwipeToDismissBox(dismiss,backgroundContent={Box(Modifier.fillMaxSize().clip(RecipeUiDefaults.CardShape).background(MaterialTheme.colorScheme.errorContainer),contentAlignment=Alignment.CenterEnd){Text("이번 목록에서 숨기기",Modifier.padding(20.dp))}},
                        enableDismissFromStartToEnd=false,modifier=Modifier.clip(RecipeUiDefaults.CardShape)) {RecipeCard(dishes,dish,onDishClick)}
                } else RecipeCard(dishes,dish,onDishClick)
            }
        }
    }
}

@Composable
fun RecipeCard(dishes:DishViewModel,dish:Dish,onDishClick:(Dish)->Unit) {
    val liked=dishes.isFavorite(dish.id)
    val known=dishes.isSuggested(dish.id)
    Surface(Modifier.fillMaxWidth().testTag("recipe-card-${dish.id}").clickable(role=Role.Button,onClickLabel="영상과 레시피 보기"){onDishClick(dish)},
        shape=RecipeUiDefaults.CardShape,border=BorderStroke(1.dp,MaterialTheme.colorScheme.outlineVariant),color=MaterialTheme.colorScheme.surface) {
        Column {
            Box {
                RecipeImage(dish.name,dish.thumbnailUrl,Modifier.fillMaxWidth().aspectRatio(2f).testTag("recipe-image-${dish.id}"),playMark=true)
                Surface(shape=RoundedCornerShape(24.dp),color=MaterialTheme.colorScheme.surface.copy(alpha=.94f),modifier=Modifier.align(Alignment.TopEnd).padding(10.dp)) {
                    IconButton(onClick={dishes.toggleFavorite(dish)},modifier=Modifier.testTag("recipe-bookmark-${dish.id}")) {
                        Icon(painterResource(if(liked)R.drawable.ic_ui_heart_filled else R.drawable.ic_ui_heart),
                            contentDescription=if(liked)"즐겨찾기 해제" else "즐겨찾기 추가",tint=MaterialTheme.colorScheme.primary,modifier=Modifier.size(22.dp))
                    }
                }
            }
            Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically) {
                    Text(dish.name,Modifier.weight(1f),fontSize=18.sp,style=MaterialTheme.typography.titleMedium,maxLines=2,overflow=TextOverflow.Ellipsis)
                    if(dish.category.isNotBlank()) {Spacer(Modifier.width(10.dp))
                        Text(dish.category,style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)}
                }
                val missing=dish.missing
                Row(verticalAlignment=Alignment.CenterVertically) {
                Text(if(!known)"재고 조건을 다시 확인해 주세요" else if(missing.isEmpty())"핵심 재료가 다 있어요" else {
                    val rest=(missing.size-2).coerceAtLeast(0)
                    "부족한 핵심 재료 ${missing.size}개 · ${missing.take(2).joinToString(", ")}"+if(rest>0)" 외 ${rest}개" else ""
                },modifier=Modifier.weight(1f).testTag("recipe-missing-${dish.id}"),style=MaterialTheme.typography.bodySmall,color=if(known&&missing.isNotEmpty())MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
                    IconButton(onClick={onDishClick(dish)}) {Icon(painterResource(R.drawable.ic_more),contentDescription="more",modifier=Modifier.size(16.dp))}
                }
            }
        }
    }
}
