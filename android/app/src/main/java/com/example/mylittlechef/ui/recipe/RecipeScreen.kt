// Photo-led list and stable scrolling assisted by Codex, 2026-11-19; human review pending.
// HE ingredient/exploration changes assisted by Codex, 2026-11-10; human review pending.
// UI ergonomics and theme changes assisted by Codex, 2026-11-03; human review pending.
// Backend data wiring added with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
// AI-assisted with Codex (GPT-6.1 Sol), 2026-10-14; human review pending.

package com.example.mylittlechef.ui.recipe

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
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.mylittlechef.R
import com.example.mylittlechef.domain.RecipeSortType
import com.example.mylittlechef.model.Recipe
import com.example.mylittlechef.viewmodel.*

@Composable
fun RecipeScreen(user: UserViewModel, fridge: FridgeViewModel, recipes: RecipeViewModel,
    onRecipeCardClick: (Recipe) -> Unit, onLikeClick: (Recipe) -> Unit, modifier: Modifier = Modifier) {
    LaunchedEffect(fridge.ingredients,user.allergies,user.utensils) {
        recipes.updateUserContext(fridge.ingredients,user.allergies,user.utensils)
        recipes.refresh(fridge.ingredients)
    }
    RecipeContent(user,fridge,recipes,onRecipeCardClick,onLikeClick,modifier)
}
enum class RecipeTab { RECOMMENDED, LIKE, AI }

@Composable
fun RecipeContent(user: UserViewModel, fridge: FridgeViewModel, recipes: RecipeViewModel,
    onRecipeCardClick: (Recipe) -> Unit, onLikeClick: (Recipe) -> Unit, modifier: Modifier = Modifier) {
    var selectedTab by rememberSaveable { mutableStateOf(RecipeTab.RECOMMENDED) }
    var showInfo by remember { mutableStateOf(false) }
    var searchText by rememberSaveable(recipes.searchQuery) { mutableStateOf(recipes.searchQuery) }
    var reviewName by rememberSaveable { mutableStateOf<String?>(null) }
    var aiUnknownPrompt by remember { mutableStateOf(false) }
    val keyboard=LocalSoftwareKeyboardController.current
    val search={ keyboard?.hide(); recipes.search(searchText,fridge.ingredients) }
    val visible=when(selectedTab) {
        RecipeTab.RECOMMENDED -> recipes.sortedRecommended(fridge.ingredients)
        RecipeTab.LIKE -> recipes.liked(user.likes,fridge.ingredients)
        RecipeTab.AI -> recipes.cachedAiRecipes(fridge.ingredients)
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
                OutlinedTextField(searchText,{searchText=it.take(100)},singleLine=true,
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
                listOf(RecipeTab.RECOMMENDED to "추천",RecipeTab.LIKE to "즐겨찾기",RecipeTab.AI to "AI 제안").forEach { (tab,label) ->
                    if(tab!=RecipeTab.AI||recipes.supportsBatchRevision||recipes.usesSelectedRevision) {
                        Column(horizontalAlignment=Alignment.CenterHorizontally) {
                            TextButton(onClick={selectedTab=tab}) { Text(label,style=MaterialTheme.typography.labelMedium,
                                color=if(selectedTab==tab) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant) }
                            HorizontalDivider(Modifier.width(if(tab==RecipeTab.LIKE) 64.dp else 48.dp),thickness=2.dp,
                                color=if(selectedTab==tab) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.background)
                        }
                    }
                }
            }
            Row(Modifier.fillMaxWidth().padding(horizontal=20.dp),verticalAlignment=Alignment.CenterVertically) {
                if(selectedTab==RecipeTab.RECOMMENDED) TextButton(onClick={recipes.otherRecommendations(fridge.ingredients)},
                    enabled=recipes.fullSearchSupported&&recipes.hasMoreRecommendations&&!recipes.isLoading) {
                    Icon(painterResource(R.drawable.ic_ui_refresh),contentDescription=null,modifier=Modifier.size(16.dp))
                    Spacer(Modifier.width(5.dp)); Text("다른 추천 보기",style=MaterialTheme.typography.labelMedium)
                }
                Spacer(Modifier.weight(1f)); RecipeSortDropdown(recipes.sortType,recipes::selectSort)
            }
            AnimatedVisibility(recipes.isLoading,enter=fadeIn(tween(140)),exit=fadeOut(tween(100))) {
                Column { LinearProgressIndicator(Modifier.fillMaxWidth().testTag("recipe-list-progress"))
                    Text("레시피를 불러오고 있어요…",Modifier.padding(horizontal=20.dp,vertical=4.dp),style=MaterialTheme.typography.bodySmall) }
            }
            recipes.error?.let { message -> Row(Modifier.padding(horizontal=20.dp),verticalAlignment=Alignment.CenterVertically) {
                Text(message,Modifier.weight(1f),style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.error)
                TextButton(onClick={recipes.refresh(fridge.ingredients)}) {Text("다시 시도")}
            } }
            if(selectedTab==RecipeTab.RECOMMENDED) {
                if(!recipes.fullSearchSupported) Text("불러온 목록에서 검색해요.",Modifier.padding(horizontal=20.dp),style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                if(recipes.fullSearchSupported&&!recipes.hasMoreRecommendations&&!recipes.isLoading&&recipes.error==null)
                    Text("현재 조건의 후보를 모두 봤어요.",Modifier.padding(horizontal=20.dp),style=MaterialTheme.typography.bodySmall)
                recipes.unregisteredIngredients.take(3).forEach { item -> TextButton(onClick={reviewName=item.name}) {
                    Text("이름 확인: ${item.name}",maxLines=1,overflow=TextOverflow.Ellipsis)
                } }
                if(recipes.lastHiddenRecipe!=null) Row(Modifier.padding(horizontal=20.dp),verticalAlignment=Alignment.CenterVertically) {
                    Text("이번 목록에서 숨겼어요.",Modifier.weight(1f),style=MaterialTheme.typography.bodySmall)
                    TextButton(onClick=recipes::undoHideRecipe) {Text("실행 취소")}
                }
            }
            if(!recipes.isLoading&&recipes.error==null&&visible.isEmpty()) Box(Modifier.weight(1f).fillMaxWidth(),contentAlignment=Alignment.Center) {
                Text(when(selectedTab) {RecipeTab.LIKE->"즐겨찾기한 레시피가 없어요.";RecipeTab.AI->"현재 재료로 받은 AI 제안이 없어요.";else->"검색 조건에 맞는 레시피가 없어요."},
                    Modifier.padding(24.dp),color=MaterialTheme.colorScheme.onSurfaceVariant)
            } else Box(Modifier.weight(1f)) {RecipeCardList(user,fridge,visible,recipes.sortType,recipes::selectSort,onRecipeCardClick,onLikeClick,false,
                if(selectedTab==RecipeTab.RECOMMENDED) ({recipes.hideRecipe(it.id)}) else null)}
        }
        if(recipes.supportsBatchRevision&&!recipes.usesSelectedRevision&&selectedTab==RecipeTab.RECOMMENDED) {
            Button(onClick={recipes.requestBatchRevision();aiUnknownPrompt=recipes.unregisteredForAI.isNotEmpty()},enabled=recipes.canRequestBatchRevision,
                modifier=Modifier.align(Alignment.BottomEnd).padding(16.dp).heightIn(min=52.dp),shape=RoundedCornerShape(15.dp)) {
                Text(if(recipes.batchRevisionLoading) "AI 제안을 만들고 있어요…" else "AI 레시피 제안 받기")
            }
        }
    }
    reviewName?.let { name -> IngredientNameReviewDialog(name,recipes.unregisteredIngredients.find {it.name==name}?.suggestions.orEmpty(),recipes.catalogNames,fridge) {reviewName=null} }
    if(aiUnknownPrompt&&recipes.unregisteredForAI.isNotEmpty()) AlertDialog(onDismissRequest={aiUnknownPrompt=false},title={Text("AI에 전달할 재료 확인")},
        text={Text("연결되지 않은 재료: ${recipes.unregisteredForAI.joinToString(", ")}\n이 항목을 제외하고 요청할까요? 냉장고에서는 삭제하지 않아요.")},
        confirmButton={TextButton(onClick={aiUnknownPrompt=false;recipes.requestBatchSkippingUnregistered()}) {Text("이 재료 없이 요청")}},
        dismissButton={TextButton(onClick={aiUnknownPrompt=false}) {Text("취소")}})
    if(showInfo) AlertDialog(onDismissRequest={showInfo=false},title={Text("레시피 안내")},text={Column(Modifier.verticalScroll(rememberScrollState()),verticalArrangement=Arrangement.spacedBy(12.dp)) {
        Text("보유 재료를 기준으로 레시피를 골랐어요. 일부 기본 조미료는 보유한 것으로 가정해요. 수량은 직접 확인해 주세요.")
        Text(if(recipes.usesSelectedRevision) "AI 제안은 상세에서 ‘내 재료로 바꾸기’를 눌렀을 때 요청해요. 원본은 그대로 유지해요." else "AI 제안은 목록 버튼으로 요청해요. 서버가 수정할 레시피를 선택해요.")
        Text("현재 알레르기·조리도구 조건은 서버 추천에 반영되지 않아요.")
        Text("받은 AI 제안은 앱 실행 중 같은 재고 조건에서 재사용해요.")
        recipes.batchRevisionMessage?.let {Text(it)}
    }},confirmButton={TextButton(onClick={showInfo=false}) {Text("확인")}})
}

@Composable
fun RecipeCardList(user: UserViewModel,fridge: FridgeViewModel,recipes: List<Recipe>,sortType: RecipeSortType,
    onSortSelected:(RecipeSortType)->Unit,onRecipeCardClick:(Recipe)->Unit,onLikeClick:(Recipe)->Unit,
    showSort:Boolean=true,onHide:((Recipe)->Unit)?=null) {
    val listState=rememberLazyListState()
    Column(Modifier.fillMaxSize()) {
        if(showSort) RecipeSortDropdown(sortType,onSortSelected,Modifier.align(Alignment.End))
        LazyColumn(state=listState,contentPadding=PaddingValues(start=20.dp,end=20.dp,top=10.dp,bottom=88.dp),
            verticalArrangement=Arrangement.spacedBy(18.dp),modifier=Modifier.fillMaxSize().testTag("recipe-list")) {
            items(recipes,key={it.id}) {recipe ->
                Box(Modifier.animateItem(fadeInSpec=tween(160),fadeOutSpec=tween(100))) {
                    if(onHide!=null) {
                        val dismiss=rememberSwipeToDismissBoxState(confirmValueChange={value->if(value==SwipeToDismissBoxValue.EndToStart){onHide(recipe);true}else false})
                        SwipeToDismissBox(dismiss,backgroundContent={Box(Modifier.fillMaxSize().clip(RoundedCornerShape(19.dp)).background(MaterialTheme.colorScheme.errorContainer),contentAlignment=Alignment.CenterEnd){Text("이번 목록에서 숨기기",Modifier.padding(20.dp))}},
                            enableDismissFromStartToEnd=false,modifier=Modifier.clip(RoundedCornerShape(19.dp))) {RecipeCard(user,fridge,recipe,onRecipeCardClick,onLikeClick)}
                    } else RecipeCard(user,fridge,recipe,onRecipeCardClick,onLikeClick)
                }
            }
        }
    }
}

@Composable
fun RecipeCard(user:UserViewModel,fridge:FridgeViewModel,recipe:Recipe,onRecipeCardClick:(Recipe)->Unit,onLikeClick:(Recipe)->Unit,imageSize:Dp=96.dp) {
    Surface(Modifier.fillMaxWidth().testTag("recipe-card-${recipe.id}").clickable(role=Role.Button,onClickLabel="레시피 상세 보기"){onRecipeCardClick(recipe)},
        shape=RoundedCornerShape(19.dp),border=BorderStroke(1.dp,MaterialTheme.colorScheme.outlineVariant),color=MaterialTheme.colorScheme.surface) {
        Column {
            Box {
                RecipeImage(recipe,Modifier.fillMaxWidth().aspectRatio(2f).testTag("recipe-image-${recipe.id}"))
                Surface(shape=RoundedCornerShape(24.dp),color=MaterialTheme.colorScheme.surface.copy(alpha=.94f),modifier=Modifier.align(Alignment.TopEnd).padding(10.dp)) {
                    IconButton(onClick={if(recipe.id in user.likes)user.removeLikes(recipe.id)else user.addLikes(recipe.id);onLikeClick(recipe)},
                        modifier=Modifier.testTag("recipe-bookmark-${recipe.id}")) {
                        Icon(painterResource(if(recipe.id in user.likes)R.drawable.ic_ui_heart_filled else R.drawable.ic_ui_heart),
                            contentDescription=if(recipe.id in user.likes)"즐겨찾기 해제" else "즐겨찾기 추가",tint=MaterialTheme.colorScheme.primary,modifier=Modifier.size(22.dp))
                    }
                }
            }
            Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(8.dp)) {
                Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically) {
                    Text(recipe.name,Modifier.weight(1f),fontSize=18.sp,style=MaterialTheme.typography.titleMedium,maxLines=2,overflow=TextOverflow.Ellipsis)
                    if(recipe.time>0) {Spacer(Modifier.width(10.dp));Icon(painterResource(R.drawable.ic_ui_clock),contentDescription=null,Modifier.size(14.dp),tint=MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.width(4.dp));Text("${recipe.time}분",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)}
                }
                val missing=recipe.missing ?: recipe.ingredients.filter {i->fridge.ingredients.none {it.name==i.name}}
                Row(verticalAlignment=Alignment.CenterVertically) {
                Text(if(!recipe.availabilityKnown)"재고 조건을 다시 확인해 주세요" else if(missing.isEmpty())"지금 바로 만들 수 있어요" else {
                    val rest=(missing.size-2).coerceAtLeast(0)
                    "부족한 재료 ${missing.size}개 · ${missing.take(2).joinToString(", "){it.name}}"+if(rest>0)" 외 ${rest}개" else ""
                },modifier=Modifier.weight(1f),style=MaterialTheme.typography.bodySmall,color=if(recipe.availabilityKnown&&missing.isNotEmpty())MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary)
                    IconButton(onClick={onRecipeCardClick(recipe)}) {Icon(painterResource(R.drawable.ic_more),contentDescription="more",modifier=Modifier.size(16.dp))}
                }
                if(recipe.revisionAvailable) Text("✦ AI 제안 있음",style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.tertiary)
                else if(recipe.revisionCandidate) Text("✦ AI 조정 후보",style=MaterialTheme.typography.labelSmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
}
