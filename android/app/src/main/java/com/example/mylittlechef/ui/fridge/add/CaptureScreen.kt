// Fixed camera controls assisted by Codex, 2026-11-25; human review pending.
// UI ergonomics and theme changes assisted by Codex, 2026-11-03; human review pending.
// AI-generated initial capture-flow scaffold with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
package com.example.mylittlechef.ui.fridge.add

import android.Manifest // CAMERA 권한 이름이 들어있음
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.provider.Settings // 앱 설정 화면으로 이동할 때 사용
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult // 권한 요청/사진 선택 결과를 받는 도구
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.ImageCapture
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import android.content.res.Configuration
import androidx.compose.ui.platform.LocalConfiguration
import androidx.compose.ui.platform.LocalView
import com.example.mylittlechef.domain.captureControlEdge
import com.example.mylittlechef.domain.CaptureControlEdge
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat // 권한 상태 확인
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect // 화면이 다시 보일 때(ON_RESUME) 등에 실행
import com.example.mylittlechef.R
import com.example.mylittlechef.data.sweep.SweepRecorder
import com.example.mylittlechef.ui.components.TextOnlyButton
import com.example.mylittlechef.ui.fridge.components.AddFlowHeader
import com.example.mylittlechef.ui.theme.MyLittleChefTheme
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.ui.theme.Gray

@Composable
fun CaptureScreen(
    onBackClick: () -> Unit,
    onCaptured: (Uri) -> Unit,
    onManualAddClick: () -> Unit,
    modifier: Modifier = Modifier
)
{
    val returnToPortrait=CameraOnlyRotation()
    var pendingCaptured by rememberSaveable {mutableStateOf<String?>(null)}
    val portraitConfiguration=LocalConfiguration.current.orientation==Configuration.ORIENTATION_PORTRAIT
    val finishCapture:(Uri)->Unit={uri -> returnToPortrait();pendingCaptured=uri.toString()}
    // Do not briefly render scan results in the old landscape configuration.
    LaunchedEffect(pendingCaptured,portraitConfiguration) {
        val uri=pendingCaptured
        if(uri!=null && portraitConfiguration) {pendingCaptured=null;onCaptured(Uri.parse(uri))}
    }
    val context = LocalContext.current

    // 지금 카메라 권한이 허용돼 있는지 확인
    fun checkCameraPermission() =
        ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) ==
                PackageManager.PERMISSION_GRANTED

    var hasCameraPermission by remember { mutableStateOf(checkCameraPermission()) }

    // 권한 요청 팝업. 사용자가 선택하면 결과(granted)가 들어옴
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission()
    ) { granted -> hasCameraPermission = granted }

    // 화면에 처음 들어왔을 때 권한이 없으면 한 번 요청
    LaunchedEffect(Unit) {
        if (!hasCameraPermission) permissionLauncher.launch(Manifest.permission.CAMERA)
    }
    // 설정 화면에서 권한을 허용하고 돌아왔을 때를 대비해 화면이 다시 보일 때마다 재확인
    LifecycleEventEffect(Lifecycle.Event.ON_RESUME) {
        hasCameraPermission = checkCameraPermission()
    }

    // 갤러리에서 사진 고르기 (시스템 사진 선택기라서 저장소 권한이 필요 없음)
    val galleryLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.PickVisualMedia()
    ) { uri -> if (uri != null) finishCapture(uri) } // 선택을 취소하면 uri가 null

    // 촬영 기능. 화면이 다시 그려져도 같은 객체를 쓰도록 remember
    val imageCapture = remember {
        ImageCapture.Builder()
            .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY) // 빠른 촬영 우선
            .build()
    }
    var isCapturing by remember { mutableStateOf(false) } // 촬영 중 중복 클릭 방지

    // 동영상 모드: 몇 초간 훑으면서 선명한 프레임 여러 장을 고른다. 사진 모드는 그대로다.
    var videoMode by remember { mutableStateOf(false) }
    var sweepProgress by remember { mutableStateOf<Float?>(null) }
    val sweepRecorder = remember { SweepRecorder(context) }
    CaptureOutputOrientation(imageCapture,sweepRecorder.analysis)
    DisposableEffect(sweepRecorder) { onDispose { sweepRecorder.cancel() } }

    CaptureContent(
        modifier=modifier,
        hasCameraPermission = hasCameraPermission,
        isCapturing = isCapturing || pendingCaptured!=null,
        videoMode = videoMode,
        sweepProgress = sweepProgress,
        onModeChange = { videoMode = it },
        onBackClick = {returnToPortrait();onBackClick()},
        onManualAddClick = {returnToPortrait();onManualAddClick()},
        onShutterClick = {
            if (!isCapturing && videoMode) {
                isCapturing = true
                sweepProgress = 0f
                sweepRecorder.start(
                    onProgress = { sweepProgress = it },
                    onDone = { uri ->
                        isCapturing = false
                        sweepProgress = null
                        if (uri != null) {
                            finishCapture(uri)
                        } else {
                            Toast.makeText(context, "촬영에 실패했어요. 다시 시도해 주세요", Toast.LENGTH_SHORT).show()
                        }
                    }
                )
            } else if (!isCapturing) {
                isCapturing = true
                takePhoto(
                    context = context,
                    imageCapture = imageCapture,
                    onSaved = { uri ->
                        isCapturing = false
                        finishCapture(uri)
                    },
                    onError = {
                        isCapturing = false
                        Toast.makeText(context, "촬영에 실패했어요. 다시 시도해 주세요", Toast.LENGTH_SHORT).show()
                    }
                )
            }
        },
        onGalleryClick = {
            galleryLauncher.launch(
                PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly) // 이미지만 선택
            )
        },
        onOpenSettingsClick = {
            // 권한을 거부한 경우 앱 설정 화면으로 보내서 직접 허용하게 함
            context.startActivity(
                Intent(
                    Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
                    Uri.fromParts("package", context.packageName, null)
                )
            )
        },
        cameraPreview = {
            CameraPreview(
                imageCapture = imageCapture,
                modifier = Modifier.fillMaxSize(),
                imageAnalysis = if (videoMode) sweepRecorder.analysis else null
            )
        }
    )


}

// TODO: connect to CameraX
@Composable
private fun CaptureContent(
    hasCameraPermission: Boolean,
    isCapturing: Boolean,
    videoMode: Boolean,
    sweepProgress: Float?,
    onModeChange: (Boolean) -> Unit,
    onBackClick: () -> Unit,
    onShutterClick: () -> Unit,
    onGalleryClick: () -> Unit, // TODO: connect to gallery
    onManualAddClick: () -> Unit,
    onOpenSettingsClick: () -> Unit,
    cameraPreview: @Composable () -> Unit,
    modifier: Modifier = Modifier
)
{
    val landscape=LocalConfiguration.current.orientation==Configuration.ORIENTATION_LANDSCAPE
    val rotation=LocalView.current.display?.rotation ?: 0
    val edge=captureControlEdge(landscape,rotation)
    Box(modifier.fillMaxSize().background(Color.Black).safeDrawingPadding().testTag("capture-screen")) {
        Box(Modifier.fillMaxSize().testTag("capture-viewfinder")) {
            if(hasCameraPermission) cameraPreview()
            else PermissionNeeded(onOpenSettingsClick,Modifier.align(Alignment.Center))
        }
        val railWidth=112.dp
        val horizontalInsets=if(landscape) railWidth else 0.dp
        Column(Modifier.align(Alignment.TopCenter).fillMaxWidth()
            .padding(start=if(edge==CaptureControlEdge.LEFT) horizontalInsets else 0.dp,
                end=if(edge==CaptureControlEdge.RIGHT) horizontalInsets else 0.dp)
            .background(Color.Black.copy(alpha=.55f))) {
            Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.CenterVertically) {
                IconButton(onClick=onBackClick) {
                    Icon(painterResource(R.drawable.ic_back),"돌아가기",tint=Color.White)
                }
                Text("추가할 재료를 찍어 주세요",Modifier.weight(1f),color=Color.White,
                    style=MaterialTheme.typography.titleMedium,maxLines=2)
            }
            ModeSwitch(videoMode,!isCapturing,onModeChange,
                Modifier.align(Alignment.CenterHorizontally).testTag("capture-mode-switch"))
        }
        val controlsModifier=when(edge) {
            CaptureControlEdge.BOTTOM -> Modifier.align(Alignment.BottomCenter).fillMaxWidth().height(112.dp)
            CaptureControlEdge.RIGHT -> Modifier.align(Alignment.CenterEnd).fillMaxHeight().width(112.dp)
            CaptureControlEdge.LEFT -> Modifier.align(Alignment.CenterStart).fillMaxHeight().width(112.dp)
        }.background(Color.Black.copy(alpha=.65f)).testTag("capture-controls-${edge.name}")
        val gallery:@Composable ()->Unit={
            IconButton(onClick=onGalleryClick,enabled=!isCapturing,modifier=Modifier.testTag("capture-gallery")) {
                Icon(painterResource(R.drawable.ic_gallery),"갤러리에서 선택",tint=Color.White)
            }
        }
        val manual:@Composable ()->Unit={
            TextButton(onClick=onManualAddClick,enabled=!isCapturing,modifier=Modifier.testTag("capture-manual")) {
                Text("직접 입력",color=Color.White,style=MaterialTheme.typography.labelMedium)
            }
        }
        if(landscape) Column(controlsModifier.padding(vertical=12.dp),
            horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.SpaceEvenly) {
            Box(Modifier.weight(1f),contentAlignment=Alignment.Center) {gallery()}
            ShutterButton(hasCameraPermission&&!isCapturing,onShutterClick)
            Box(Modifier.weight(1f),contentAlignment=Alignment.Center) {manual()}
        } else Row(controlsModifier.padding(horizontal=12.dp),verticalAlignment=Alignment.CenterVertically) {
            Box(Modifier.weight(1f),contentAlignment=Alignment.Center) {gallery()}
            ShutterButton(hasCameraPermission&&!isCapturing,onShutterClick)
            Box(Modifier.weight(1f),contentAlignment=Alignment.Center) {manual()}
        }
        if(sweepProgress!=null) Column(
            Modifier.align(Alignment.BottomCenter)
                .padding(start=if(edge==CaptureControlEdge.LEFT) 128.dp else 24.dp,
                    end=if(edge==CaptureControlEdge.RIGHT) 128.dp else 24.dp,
                    bottom=if(landscape) 16.dp else 128.dp)
                .background(Color.Black.copy(alpha=.65f)).padding(12.dp),
            horizontalAlignment=Alignment.CenterHorizontally) {
            Text("냉장고를 천천히 훑어 주세요",color=Color.White,style=MaterialTheme.typography.bodyMedium)
            LinearProgressIndicator(progress={sweepProgress},modifier=Modifier.fillMaxWidth().padding(top=8.dp),
                color=Color.White,trackColor=Color.White.copy(alpha=.3f))
        }
    }
}

@Composable
private fun ModeSwitch(
    videoMode: Boolean,
    enabled: Boolean,
    onModeChange: (Boolean) -> Unit,
    modifier: Modifier = Modifier
)
{
    Row(modifier = modifier)
    {
        listOf(false to "사진", true to "동영상").forEach { (isVideo, label) ->
            TextButton(
                onClick = { onModeChange(isVideo) },
                modifier=Modifier.testTag(if(isVideo) "capture-mode-video" else "capture-mode-photo").semantics {selected=videoMode==isVideo},
                enabled = enabled
            )
            {
                Text(
                    text = label,
                    color = Color.White.copy(alpha = if (videoMode == isVideo) 1f else 0.6f),
                    style = MaterialTheme.typography.labelMedium,
                    textDecoration = if (videoMode == isVideo) TextDecoration.Underline else null
                )
            }
        }
    }
}

@Composable
private fun ShutterButton(
    enabled: Boolean,
    onClick: () -> Unit
)
{
    Box(
        modifier = Modifier
            .size(50.dp)
            .testTag("capture-shutter")
            .clip(CircleShape)
            // Camera overlay controls keep a white shutter against the dark viewfinder.
            .background(Color.White)
            .clickable(
                enabled = enabled,
                role = Role.Button,
                onClickLabel = "shutter",
                onClick = onClick
            )
    )
}

@Composable
private fun PermissionNeeded(
    onOpenSettingsClick: () -> Unit,
    modifier: Modifier = Modifier
)
{
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally
    )
    {
        Text(
            text = "카메라 권한이 필요해요",
            color = Color.White,
            style = MaterialTheme.typography.bodyMedium
        )
        TextButton(
            onClick = onOpenSettingsClick
        )
        {
            Text(
                text = "설정에서 허용하기",
                color = Color.White,
                style = MaterialTheme.typography.labelMedium,
                textDecoration = TextDecoration.Underline
            )
        }
    }
}

// TODO: camera guide area

//@Preview(showBackground = true, name = "camera available")
//@Composable
//private fun CaptureScreenPreview(
//
//)
//{
//
//}
//
//@Preview(showBackground = true, name = "no permission")
//@Composable
//private fun CaptureContentNoPermissionPreview(
//
//)
//{
//
//}
