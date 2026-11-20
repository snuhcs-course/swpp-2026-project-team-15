// Actual-screen spotlight tour assisted by Codex, 2026-11-19; human review pending.
package com.example.mylittlechef.ui.help

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.composed
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.graphics.*
import androidx.compose.ui.layout.boundsInWindow
import androidx.compose.ui.layout.onGloballyPositioned
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.data.local.SectionTourRepository
import com.example.mylittlechef.navigation.Routes
import kotlinx.coroutines.launch

@Stable
class TourAnchors {
    val bounds=mutableStateMapOf<String,Rect>()
    var launch: () -> Unit = {}
}
val LocalSectionTour=staticCompositionLocalOf<TourAnchors?> { null }
fun Modifier.tourAnchor(name: String): Modifier = composed {
    val tour=LocalSectionTour.current
    DisposableEffect(tour,name) { onDispose { tour?.bounds?.remove(name) } }
    onGloballyPositioned { tour?.bounds?.set(name,it.boundsInWindow()) }
}
private data class TourStep(val route:String,val anchor:String,val title:String,val body:String)
private val steps=listOf(
    TourStep(Routes.FRIDGE,"fridge-add","재료부터 담아볼까요?","직접 입력하거나 사진으로 추가해요. 사진 결과는 확인한 뒤 저장해요."),
    TourStep(Routes.FRIDGE,"fridge-manage","냉장고를 가볍게 정리해요","관리를 누르거나 재료를 길게 눌러 여러 개를 선택해요. 삭제 후 실행 취소도 할 수 있어요."),
    TourStep(Routes.RECIPE,"recipe-browse","오늘의 한 끼를 찾아요","받은 목록에서 이름으로 찾고, 카드를 눌러 영상과 재료·조리 순서를 확인해요. ‘내 재료로 바꾸기’는 원본을 내 재료에 맞게 조정해요."),
    TourStep(Routes.PROFILE,"profile-pantry","내게 맞는 설정을 모아뒀어요","기본 재료·조미료와 조리도구, 알레르기를 수정해요. 사용 안내에서 다시 둘러볼 수 있어요.")
)
@Composable
fun SectionTourHost(repository: SectionTourRepository, currentRoute: String?, navigate: (String)->Unit, automaticEnabled: Boolean = true,
    content: @Composable ()->Unit) {
    val seen by repository.seenVersion.collectAsState(initial=-1)
    val anchors=remember { TourAnchors() }
    var step by rememberSaveable { mutableIntStateOf(-1) }
    var returnRoute by rememberSaveable { mutableStateOf(Routes.FRIDGE) }
    var saving by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf(false) }
    val scope=rememberCoroutineScope()
    LaunchedEffect(seen,automaticEnabled) { if(automaticEnabled && seen==0 && step<0) { returnRoute=Routes.FRIDGE;step=0 } }
    SideEffect { anchors.launch={returnRoute=currentRoute ?: Routes.PROFILE;step=0} }
    LaunchedEffect(step) { if(step in steps.indices) navigate(steps[step].route) }
    fun finish() {
        if(saving)return
        saving=true;error=false
        scope.launch {
            try { repository.markSeen(); step=-1; navigate(returnRoute) }
            catch (cancelled: kotlinx.coroutines.CancellationException) { throw cancelled }
            catch (_: Exception) { error=true }
            finally { saving=false }
        }
    }
    BackHandler(enabled=step>=0) { finish() }
    var origin by remember { mutableStateOf(androidx.compose.ui.geometry.Offset.Zero) }
    CompositionLocalProvider(LocalSectionTour provides anchors) {
        Box(Modifier.fillMaxSize().onGloballyPositioned { origin=it.boundsInWindow().topLeft }) {
            Box(if(step>=0) Modifier.fillMaxSize().clearAndSetSemantics {} else Modifier.fillMaxSize()) { content() }
            if(step in steps.indices) {
                val item=steps[step]
                val target=anchors.bounds[item.anchor]?.translate(-origin.x,-origin.y)
                val density=LocalDensity.current
                BoxWithConstraints(Modifier.fillMaxSize().testTag("section-tour").clickable(indication=null,
                    interactionSource=remember { androidx.compose.foundation.interaction.MutableInteractionSource() }) {}) {
                    Canvas(Modifier.fillMaxSize()) {
                        val mask=Path().apply {
                            fillType=PathFillType.EvenOdd
                            addRect(Rect(0f,0f,size.width,size.height))
                            target?.let { addRoundRect(androidx.compose.ui.geometry.RoundRect(it.inflate(5.dp.toPx()),CornerRadius(14.dp.toPx()))) }
                        }
                        drawPath(mask,Color.Black.copy(alpha=.68f))
                        target?.let { drawRoundRect(Color.White,it.topLeft,it.size,CornerRadius(12.dp.toPx()),style=androidx.compose.ui.graphics.drawscope.Stroke(2.dp.toPx())) }
                    }
                    // Keep the callout away from a bottom target; never require a populated list.
                    val bottomTarget=target!=null && target.center.y>with(density){maxHeight.toPx()}*.52f
                    Surface(Modifier.align(if(bottomTarget) Alignment.TopCenter else Alignment.BottomCenter)
                        .padding(horizontal=20.dp,vertical=64.dp).fillMaxWidth(),shape=RoundedCornerShape(22.dp),
                        color=MaterialTheme.colorScheme.surface) {
                        Column(Modifier.padding(20.dp),verticalArrangement=Arrangement.spacedBy(10.dp)) {
                            Text("앱 둘러보기  ${step+1}/${steps.size}",style=MaterialTheme.typography.labelMedium,color=MaterialTheme.colorScheme.primary)
                            Text(item.title,style=MaterialTheme.typography.titleLarge)
                            Text(item.body,style=MaterialTheme.typography.bodyMedium)
                            if(error) Text("안내 완료를 저장하지 못했어요. 다시 눌러 주세요.",color=MaterialTheme.colorScheme.error)
                            Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically) {
                                TextButton(onClick={finish()},enabled=!saving,modifier=Modifier.testTag("skip-section-tour")){Text("건너뛰기")}
                                Spacer(Modifier.weight(1f))
                                if(step>0) TextButton(onClick={step--},enabled=!saving){Text("이전")}
                                Button(onClick={if(step==steps.lastIndex)finish() else step++},enabled=!saving,
                                    modifier=Modifier.testTag("next-section-tour")) { Text(if(saving) "저장 중" else if(step==steps.lastIndex) "시작하기" else "다음") }
                            }
                        }
                    }
                }
            }
        }
    }
}
