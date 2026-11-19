// Photo-led detail layout assisted by Codex, 2026-11-19; human review pending.
// HE selected-recipe state, consent, cancellation and cooking completion retained.
// HE ingredient/exploration changes assisted by Codex, 2026-11-10; human review pending.
// Cached deployed batch suggestions assisted by Codex, 2026-11-03; human review pending.

package com.example.mylittlechef.ui.recipe

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.text
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.mylittlechef.R
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import com.example.mylittlechef.ui.components.IngredientBadge
import com.example.mylittlechef.viewmodel.*
import kotlinx.coroutines.launch

@Composable
fun RecipeDetailScreen(user:UserViewModel,recipe:Recipe,onBackClick:()->Unit,onLikeClick:()->Unit,
    revisionState:RevisionUiState=RevisionUiState(),onRequestRevision:(()->Unit)?=null,batchRevision:Boolean=false,
    fridge:FridgeViewModel?=null,selectedState:SelectedRevisionState?=null,onCancelRevision:()->Unit={},
    onReviewIngredients:()->Unit={},onIgnoreUnknown:()->Unit={},onReloadRecipes:()->Unit={}) {
    var showSuggestion by rememberSaveable(recipe.id) {mutableStateOf(false)}
    var showCompletion by rememberSaveable(recipe.id) {mutableStateOf(false)}
    val base=selectedState?.original ?: recipe
    val shown=if(selectedState!=null) {
        if(showSuggestion&&selectedState.status==RevisionStatus.REVISED) selectedState.suggestion?:base else base
    } else if(showSuggestion&&revisionState.status==RevisionStatus.REVISED) revisionState.recipe?:recipe else recipe
    val scope=rememberCoroutineScope();val anchor=remember {BringIntoViewRequester()}
    val scroll=rememberScrollState()
    val pinned by remember {derivedStateOf {scroll.value>180}}
    val headerColor by animateColorAsState(if(pinned)MaterialTheme.colorScheme.background else Color.Transparent,tween(160),label="detail-header")
    fun leave(){if(selectedState?.status==RevisionStatus.LOADING)onCancelRevision();onBackClick()}
    BackHandler(enabled=selectedState!=null) {leave()}
    if(showCompletion&&fridge!=null)CookingCompletionDialog(shown,fridge){showCompletion=false}
    Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).statusBarsPadding().navigationBarsPadding()) {
        Column(Modifier.fillMaxSize().verticalScroll(scroll).testTag("recipe-detail-scroll")) {
            RecipeImage(recipe,Modifier.fillMaxWidth().height(236.dp).testTag("recipe-detail-photo"))
            Column(Modifier.fillMaxWidth().padding(20.dp),verticalArrangement=Arrangement.spacedBy(16.dp)) {
                Text("오늘의 한 끼",style=MaterialTheme.typography.labelMedium,color=MaterialTheme.colorScheme.primary)
                Text(shown.name,fontSize=26.sp,fontWeight=FontWeight.SemiBold,lineHeight=34.sp)
                Row(horizontalArrangement=Arrangement.spacedBy(16.dp),verticalAlignment=Alignment.CenterVertically) {
                    if(recipe.time>0)RecipeMeta(recipe.time)
                    shown.servingText?.let {Text(if(showSuggestion&&shown!==base)"제안 분량: $it" else "원본 분량: $it",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)}
                }
                val missing=if(shown.availabilityKnown)shown.missing.orEmpty().map{it.name}.toSet()else emptySet()
                Box(Modifier.bringIntoViewRequester(anchor)) {RecipeIngredients(shown.ingredients,shown.ingredientQuantities,missing,shown.availabilityKnown)}
                if(selectedState!=null) {
                    Surface(color=MaterialTheme.colorScheme.surfaceVariant,shape=RoundedCornerShape(16.dp)) {
                        Box(Modifier.fillMaxWidth().padding(16.dp)) {
                            SelectedRevisionPanel(selectedState,showSuggestion,
                                onRequest={showSuggestion=true;onRequestRevision?.invoke()},onToggle={showSuggestion=!showSuggestion},onCancel=onCancelRevision,
                                onOriginal={showSuggestion=false;scope.launch{anchor.bringIntoView()}},onReview=onReviewIngredients,
                                onIgnore={showSuggestion=true;onIgnoreUnknown()},onReload=onReloadRecipes)
                        }
                    }
                } else if(onRequestRevision!=null) {
                    Surface(color=MaterialTheme.colorScheme.surfaceVariant,shape=RoundedCornerShape(16.dp)) {
                        Column(Modifier.padding(16.dp),verticalArrangement=Arrangement.spacedBy(10.dp)) {
                            Text(if(shown===recipe)"원본 레시피"else"AI 수정 제안",style=MaterialTheme.typography.titleMedium)
                            if(batchRevision) Text("AI 요청은 목록에서 할 수 있어요. 서버가 수정할 레시피를 선택해요.",style=MaterialTheme.typography.bodySmall)
                            if(!recipe.availabilityKnown)Text("원본의 재료 보유 조건을 다시 확인해 주세요.")
                            if((batchRevision&&revisionState.status==RevisionStatus.REVISED)||(!batchRevision&&recipe.availabilityKnown&&recipe.revisionCandidate)) {
                                OutlinedButton(enabled=revisionState.status!=RevisionStatus.LOADING,onClick={
                                    if(showSuggestion&&revisionState.status==RevisionStatus.REVISED)showSuggestion=false
                                    else{showSuggestion=true;if(!batchRevision)onRequestRevision()}
                                }) {Text(when{revisionState.status==RevisionStatus.LOADING->"AI 제안을 만들고 있어요…";showSuggestion&&revisionState.status==RevisionStatus.REVISED->"원본 보기";revisionState.status==RevisionStatus.ERROR->"AI 제안 다시 시도";else->"AI 제안 보기"})}
                            }
                            if(showSuggestion||revisionState.status in listOf(RevisionStatus.REFUSED,RevisionStatus.ERROR))revisionState.message?.let{Text(it)}
                            if(showSuggestion&&revisionState.status==RevisionStatus.REVISED){revisionState.changes.forEach{Text("• $it")};Text("AI 제안은 직접 확인해 주세요. 조리 시간은 원본 기준이에요.",style=MaterialTheme.typography.bodySmall)}
                            Text("알레르기·조리도구 조건은 반영되지 않아요.",style=MaterialTheme.typography.bodySmall)
                        }
                    }
                }
                RecipeSteps(shown.steps)
                if(fridge!=null) {
                    Button(onClick={showCompletion=true},modifier=Modifier.fillMaxWidth().heightIn(min=52.dp),shape=RoundedCornerShape(13.dp)) {Text("요리 완료")}
                    Text("다 쓴 재료만 골라 냉장고를 정리해요.",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Spacer(Modifier.height(24.dp))
            }
        }
        Row(Modifier.fillMaxWidth().background(headerColor).padding(horizontal=12.dp,vertical=4.dp),verticalAlignment=Alignment.CenterVertically) {
            Surface(shape=RoundedCornerShape(24.dp),color=MaterialTheme.colorScheme.surface.copy(alpha=.94f)) {
                IconButton(onClick=::leave) {Icon(painterResource(R.drawable.ic_back),contentDescription="back",modifier=Modifier.size(20.dp))}
            }
            Box(Modifier.weight(1f).padding(horizontal=12.dp)) {androidx.compose.animation.AnimatedVisibility(pinned,enter=fadeIn(tween(140)),exit=fadeOut(tween(100))) {Text(recipe.name,style=MaterialTheme.typography.titleMedium,maxLines=1)}}
            RecipeDetailBookmark(user,recipe,onLikeClick)
        }
    }
}

@Composable
private fun RecipeDetailBookmark(user:UserViewModel,recipe:Recipe,onLikeClick:()->Unit) {
    Surface(shape=RoundedCornerShape(24.dp),color=MaterialTheme.colorScheme.surface.copy(alpha=.94f)) {
        IconButton(onClick={if(recipe.id in user.likes)user.removeLikes(recipe.id)else user.addLikes(recipe.id);onLikeClick()}) {
            Icon(painterResource(if(recipe.id in user.likes)R.drawable.ic_ui_heart_filled else R.drawable.ic_ui_heart),
                contentDescription=if(recipe.id in user.likes)"즐겨찾기 해제"else"즐겨찾기 추가",tint=MaterialTheme.colorScheme.primary,modifier=Modifier.size(22.dp))
        }
    }
}

@Composable
fun RecipeDetailHeader(user:UserViewModel,recipe:Recipe,onBackClick:()->Unit,onLikeClick:()->Unit,modifier:Modifier=Modifier) {
    Row(modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically) {
        IconButton(onClick=onBackClick){Icon(painterResource(R.drawable.ic_back),contentDescription="back")}
        Text(recipe.name,Modifier.weight(1f),style=MaterialTheme.typography.titleMedium)
        RecipeDetailBookmark(user,recipe,onLikeClick)
    }
}
@Composable fun RecipeMeta(time:Int) {
    Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(5.dp)) {
        Icon(painterResource(R.drawable.ic_ui_clock),contentDescription=null,modifier=Modifier.size(16.dp),tint=MaterialTheme.colorScheme.onSurfaceVariant)
        Text("${time}분",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
    }
}
@Composable
fun RecipeIngredients(ingredients:List<Ingredient>,quantities:List<String?> = emptyList(),missingNames:Set<String> = emptySet(),availabilityKnown:Boolean=true) {
    Column(Modifier.fillMaxWidth()) {
        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically) {
            Text("재료",Modifier.weight(1f),fontSize=18.sp,fontWeight=FontWeight.SemiBold)
            if(availabilityKnown&&missingNames.isNotEmpty())Text("부족한 재료 ${missingNames.size}개",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.height(10.dp))
        ingredients.forEachIndexed {index,ingredient->
            val missing=ingredient.name in missingNames
            Row(Modifier.fillMaxWidth().heightIn(min=54.dp).padding(vertical=7.dp).testTag("recipe-ingredient-row-${ingredient.name}"),verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(10.dp)) {
                IngredientBadge(ingredient.name,size=36.dp)
                val readable=ingredient.name+quantities.getOrNull(index)?.takeIf{it.isNotBlank()}?.let{" $it"}.orEmpty()+if(missing) " · 부족" else ""
                // Keep the name, amount and shortage readable as one accessible phrase.
                Row(Modifier.weight(1f).clearAndSetSemantics {text=AnnotatedString(readable)},verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(10.dp)) {
                Text(ingredient.name,Modifier.weight(1f),fontSize=14.sp,lineHeight=20.sp)
                quantities.getOrNull(index)?.takeIf{it.isNotBlank()}?.let {Text(it,Modifier.widthIn(max=88.dp),style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)}
                Surface(color=if(missing)MaterialTheme.colorScheme.errorContainer else MaterialTheme.colorScheme.surfaceVariant,shape=RoundedCornerShape(6.dp)) {
                    Text(if(!availabilityKnown)"확인 필요"else if(missing)"부족"else"준비됨",Modifier.padding(horizontal=6.dp,vertical=4.dp),fontSize=11.sp,
                        color=if(missing)MaterialTheme.colorScheme.onErrorContainer else MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            }
            HorizontalDivider(color=MaterialTheme.colorScheme.outlineVariant)
        }
    }
}
@Composable fun RecipeSteps(steps:List<String>) {
    Column(Modifier.fillMaxWidth(),verticalArrangement=Arrangement.spacedBy(18.dp)) {
        Text("조리 방법",fontSize=18.sp,fontWeight=FontWeight.SemiBold)
        steps.forEachIndexed {i,step->
            val numberColor=MaterialTheme.colorScheme.primary
            Text(buildAnnotatedString {
                withStyle(SpanStyle(color=numberColor,fontWeight=FontWeight.SemiBold)) { append("${i+1}. ") }
                append(step)
            },Modifier.fillMaxWidth(),fontSize=15.sp,lineHeight=25.sp)
        }
    }
}
