// UAT stage 4 assisted by Codex, 2026-11-24; human review pending.
// Actual-screen spotlight tour assisted by Codex, 2026-11-19; human review pending.
package com.example.mylittlechef.ui.help

import com.example.mylittlechef.domain.guideCalloutZone
import androidx.compose.foundation.relocation.BringIntoViewRequester
import androidx.compose.foundation.relocation.bringIntoViewRequester
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.unit.IntOffset
import kotlin.math.roundToInt
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
    val reveal=mutableStateMapOf<String,BringIntoViewRequester>()
    var active by mutableStateOf(false)
    var launch: () -> Unit = {}
}
val LocalSectionTour=staticCompositionLocalOf<TourAnchors?> { null }
fun Modifier.tourAnchor(name: String): Modifier = composed {
    val tour=LocalSectionTour.current
    val requester=remember {BringIntoViewRequester()}
    DisposableEffect(tour,name) {
        tour?.reveal?.set(name,requester)
        onDispose { tour?.bounds?.remove(name);tour?.reveal?.remove(name) }
    }
    bringIntoViewRequester(requester).onGloballyPositioned { tour?.bounds?.set(name,it.boundsInWindow()) }
}
private data class TourStep(val route:String,val anchor:String,val title:String,val body:String)
private val steps=listOf(
    TourStep(Routes.FRIDGE,"fridge-add","재료부터 담아볼까요?","직접 입력하거나 사진으로 추가해요. 사진 결과는 확인한 뒤 저장해요."),
    TourStep(Routes.FRIDGE,"fridge-manage","냉장고를 가볍게 정리해요","관리를 누르거나 재료를 길게 눌러 여러 개를 선택해요. 길게 누른 뒤 쓸어 선택하고, 삭제 후 실행 취소도 할 수 있어요."),
    TourStep(Routes.RECIPE,"recipe-browse","오늘의 한 끼를 찾아요","목록에서 요리를 고르면 재료와 조리법을 볼 수 있어요. 상세에서 복사하거나 ‘조리 시작’으로 한 단계씩 확인해요. AI 제안은 직접 요청할 때 만들어요."),
    TourStep(Routes.PROFILE,"profile-pantry","내게 맞는 설정을 모아뒀어요","기본 재료·조미료와 화면 모드를 설정해요. 사용 안내에서 다시 둘러볼 수 있어요.")
)
@Composable
fun SectionTourHost(repository: SectionTourRepository, currentRoute: String?, navigate: (String)->Unit, automaticEnabled: Boolean = true, navigationReady: Boolean = true,
    content: @Composable ()->Unit) {
    val seen by repository.seenVersion.collectAsState(initial=-1)
    val anchors=remember { TourAnchors() }
    var step by rememberSaveable { mutableIntStateOf(-1) }
    var returnRoute by rememberSaveable { mutableStateOf(Routes.FRIDGE) }
    var saving by rememberSaveable { mutableStateOf(false) }
    var returning by rememberSaveable {mutableStateOf(false)}
    var error by remember { mutableStateOf(false) }
    val scope=rememberCoroutineScope()
    LaunchedEffect(seen,automaticEnabled) { if(automaticEnabled && seen==0 && step<0) { returnRoute=Routes.FRIDGE;step=0 } }
    SideEffect { anchors.active=step>=0; anchors.launch={returnRoute=currentRoute ?: Routes.PROFILE;returning=false;saving=false;error=false;step=0} }
    LaunchedEffect(step,returning) { if(step in steps.indices && !returning) navigate(steps[step].route) }
    val currentStep=steps.getOrNull(step)
    val reveal=currentStep?.let {anchors.reveal[it.anchor]}
    LaunchedEffect(step,currentRoute,reveal) {
        if(currentStep!=null && currentRoute==currentStep.route) reveal?.bringIntoView()
    }
    fun finish() {
        if(!saving) {saving=true;error=false}
    }
    // Keep the guide shield active through both navigation transitions. Finishing while a tab
    // is entering must not leave a new INITIALIZED destination behind an already closed guide.
    LaunchedEffect(saving,returning,currentRoute,navigationReady,step) {
        if(saving && !returning && navigationReady && currentStep?.route==currentRoute) {
            try {repository.markSeen();returning=true;navigate(returnRoute)}
            catch(cancelled:kotlinx.coroutines.CancellationException) {throw cancelled}
            catch(_:Exception) {error=true;saving=false}
        }
        if(saving && returning && navigationReady && currentRoute==returnRoute) {
            step=-1;returning=false;saving=false
        }
    }
    BackHandler(enabled=step>=0) { finish() }
    var origin by remember { mutableStateOf(androidx.compose.ui.geometry.Offset.Zero) }
    CompositionLocalProvider(LocalSectionTour provides anchors) {
        Box(Modifier.fillMaxSize().onGloballyPositioned { origin=it.boundsInWindow().topLeft }) {
            Box(if(step>=0) Modifier.fillMaxSize().clearAndSetSemantics {} else Modifier.fillMaxSize()) { content() }
            if(step in steps.indices) {
                val item=steps[step]
                val density=LocalDensity.current
                val view=LocalView.current
                val anchor=if(currentRoute==item.route) anchors.bounds[item.anchor] else null
                val target=anchor?.translate(-origin.x,-origin.y)?.takeIf {it.width>0 && it.height>0}
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
                    val height=with(density){maxHeight.toPx()}
                    val top=(WindowInsets.safeDrawing.getTop(density)-origin.y).coerceIn(0f,height)
                    val windowHeight=view.rootView.height.takeIf {it>0}?.toFloat() ?: (height+origin.y)
                    val bottom=(windowHeight-WindowInsets.safeDrawing.getBottom(density)-origin.y).coerceIn(top,height)
                    val zone=guideCalloutZone(top,bottom,target?.top,target?.bottom,with(density){12.dp.toPx()})
                    target?.let { bounds ->
                        Box(Modifier.offset {IntOffset(bounds.left.roundToInt(),bounds.top.roundToInt())}
                            .size(with(density){bounds.width.toDp()},with(density){bounds.height.toDp()})
                            .testTag("tour-highlight"))
                    }
                    val cardScroll=rememberScrollState()
                    LaunchedEffect(step) {cardScroll.scrollTo(0)}
                    Surface(Modifier.offset {IntOffset(0,zone.top.roundToInt())}
                        .padding(horizontal=20.dp).fillMaxWidth()
                        .heightIn(max=with(density){zone.height.coerceAtLeast(1f).toDp()}).testTag("tour-callout"),
                        shape=RoundedCornerShape(20.dp),color=MaterialTheme.colorScheme.surface) {
                        Column(Modifier.verticalScroll(cardScroll).testTag("tour-callout-scroll").padding(16.dp),
                            verticalArrangement=Arrangement.spacedBy(10.dp)) {
                            Text("앱 둘러보기  ${step+1}/${steps.size}",style=MaterialTheme.typography.labelMedium,color=MaterialTheme.colorScheme.primary)
                            Text(item.title,style=MaterialTheme.typography.titleLarge)
                            Text(item.body,style=MaterialTheme.typography.bodyMedium)
                            if(error) Text("안내 완료를 저장하지 못했어요. 다시 눌러 주세요.",color=MaterialTheme.colorScheme.error)
                            FlowRow(Modifier.fillMaxWidth(),horizontalArrangement=Arrangement.spacedBy(8.dp),
                                verticalArrangement=Arrangement.spacedBy(4.dp)) {
                                TextButton(onClick={finish()},enabled=!saving,modifier=Modifier.heightIn(min=48.dp).testTag("skip-section-tour")){Text("건너뛰기")}
                                if(step>0) TextButton(onClick={step--},enabled=!saving && navigationReady && currentRoute==item.route,
                                    modifier=Modifier.heightIn(min=48.dp).testTag("previous-section-tour")){Text("이전")}
                                Button(onClick={if(step==steps.lastIndex)finish() else step++},enabled=!saving && navigationReady && currentRoute==item.route,
                                    modifier=Modifier.heightIn(min=48.dp).testTag("next-section-tour")) {
                                    Text(if(saving) "닫는 중" else if(step==steps.lastIndex) "시작하기" else "다음")
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
