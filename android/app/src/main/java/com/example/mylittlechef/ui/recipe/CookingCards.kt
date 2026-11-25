// UAT stage 4 assisted by Codex, 2026-11-24; human review pending.
package com.example.mylittlechef.ui.recipe

import androidx.compose.animation.*
import androidx.compose.animation.core.MutableTransitionState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.BorderStroke
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.example.mylittlechef.domain.CookingRun

@Composable
fun CookingCards(run:CookingRun,onExit:()->Unit,onComplete:()->Unit) {
    var index by rememberSaveable(run.id) {mutableIntStateOf(0)}
    var confirmExit by rememberSaveable(run.id) {mutableStateOf(false)}
    val steps=run.recipe.steps
    val current=index.coerceIn(0,(steps.size-1).coerceAtLeast(0))
    Dialog(onDismissRequest={confirmExit=true},properties=DialogProperties(usePlatformDefaultWidth=false,
        decorFitsSystemWindows=false,dismissOnClickOutside=false)) {
        Surface(Modifier.fillMaxSize().testTag("cooking-mode"),color=MaterialTheme.colorScheme.background) {
            Column(Modifier.fillMaxSize().safeDrawingPadding().padding(20.dp),verticalArrangement=Arrangement.spacedBy(12.dp)) {
                Row(Modifier.fillMaxWidth()) {
                    Text(run.name,Modifier.weight(1f),style=MaterialTheme.typography.titleLarge)
                    TextButton(onClick={confirmExit=true},modifier=Modifier.testTag("exit-cooking")) {Text("조리 종료")}
                }
                Text(if(run.revised) "AI 수정본으로 조리 중" else "원본 레시피로 조리 중",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
                Text("${current+1} / ${steps.size} 단계",modifier=Modifier.testTag("cooking-step-number"),style=MaterialTheme.typography.titleMedium,color=MaterialTheme.colorScheme.primary)
                // Reserve the card area throughout entrance and step transitions: controls never jump.
                Box(Modifier.weight(1f).fillMaxWidth()) {
                    val entrance=remember { MutableTransitionState(false).apply { targetState=true } }
                    androidx.compose.animation.AnimatedVisibility(entrance,modifier=Modifier.fillMaxSize(),
                        enter=fadeIn(tween(220))+slideInVertically(tween(220)) {it/16}+scaleIn(tween(220),initialScale=.97f)) {
                        androidx.compose.animation.AnimatedContent(current,modifier=Modifier.fillMaxSize(),
                            transitionSpec={
                                val forward=targetState>initialState
                                (fadeIn(tween(220))+scaleIn(tween(220),initialScale=.97f)+
                                    slideInHorizontally(tween(220)) {if(forward) it/10 else -it/10}) togetherWith
                                    (fadeOut(tween(100))+slideOutHorizontally(tween(120)) {if(forward) -it/14 else it/14})
                            },label="cooking-card-transition") { step ->
                            Surface(Modifier.fillMaxSize().testTag("cooking-step-card"),shape=RecipeUiDefaults.CardShape,
                                border=BorderStroke(1.dp,MaterialTheme.colorScheme.outlineVariant),
                                color=cookingCardColor(MaterialTheme.colorScheme.surfaceVariant,step,steps.size),
                                contentColor=MaterialTheme.colorScheme.onSurface) {
                                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(20.dp)
                                    .testTag("cooking-step-scroll")) {
                                    Text(steps.getOrNull(step)?.text.orEmpty(),style=MaterialTheme.typography.titleLarge,
                                        modifier=Modifier.testTag("cooking-step-text"))
                                }
                            }
                        }
                    }
                }
                Row(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(12.dp)) {
                    OutlinedButton(onClick={index=current-1},enabled=current>0,shape=RecipeUiDefaults.ButtonShape,
                        modifier=Modifier.weight(1f).heightIn(min=RecipeUiDefaults.ControlHeight).testTag("cooking-previous")) {Text("이전")}
                    Button(onClick={if(current<steps.lastIndex) index=current+1 else onComplete()},
                        enabled=steps.isNotEmpty(),shape=RecipeUiDefaults.ButtonShape,modifier=Modifier.weight(1f).heightIn(min=RecipeUiDefaults.ControlHeight).testTag("cooking-next")) {
                        Text(if(current==steps.lastIndex) "요리 완료" else "다음")
                    }
                }
            }
        }
        if(confirmExit) AlertDialog(onDismissRequest={confirmExit=false},title={Text("조리를 끝낼까요?")},
            text={Text("냉장고 재료는 바뀌지 않아요. 다시 시작하면 첫 단계부터 보여 드려요.")},
            confirmButton={TextButton(onClick=onExit,modifier=Modifier.testTag("confirm-exit-cooking")) {Text("조리 종료")}},
            dismissButton={TextButton(onClick={confirmExit=false}) {Text("계속 조리")}})
    }
}
