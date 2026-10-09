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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat // 권한 상태 확인
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LifecycleEventEffect // 화면이 다시 보일 때(ON_RESUME) 등에 실행
import com.example.mylittlechef.R
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
    ) { uri -> if (uri != null) onCaptured(uri) } // 선택을 취소하면 uri가 null

    // 촬영 기능. 화면이 다시 그려져도 같은 객체를 쓰도록 remember
    val imageCapture = remember {
        ImageCapture.Builder()
            .setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY) // 빠른 촬영 우선
            .build()
    }
    var isCapturing by remember { mutableStateOf(false) } // 촬영 중 중복 클릭 방지

    CaptureContent(
        hasCameraPermission = hasCameraPermission,
        isCapturing = isCapturing,
        onBackClick = onBackClick,
        onManualAddClick = onManualAddClick,
        onShutterClick = {
            if (!isCapturing) {
                isCapturing = true
                takePhoto(
                    context = context,
                    imageCapture = imageCapture,
                    onSaved = { uri ->
                        isCapturing = false
                        onCaptured(uri)
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
        cameraPreview = { CameraPreview(imageCapture = imageCapture, modifier = Modifier.fillMaxSize()) }
    )


}

// TODO: connect to CameraX
@Composable
private fun CaptureContent(
    hasCameraPermission: Boolean,
    isCapturing: Boolean,
    onBackClick: () -> Unit,
    onShutterClick: () -> Unit,
    onGalleryClick: () -> Unit, // TODO: connect to gallery
    onManualAddClick: () -> Unit,
    onOpenSettingsClick: () -> Unit,
    cameraPreview: @Composable () -> Unit,
    modifier: Modifier = Modifier
)
{
    Column(
        modifier = modifier
            .fillMaxSize()
            .navigationBarsPadding()
            .background(Color.White)
    )
    {
        AddFlowHeader(
            onBackClick = onBackClick,
            title = "추가할 재료들을 찍어 주세요"
        )

        // camera area
        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .background(Gray)
        )
        {
            if (hasCameraPermission) {
                cameraPreview()
            }
            else {
                PermissionNeeded(
                    onOpenSettingsClick = onOpenSettingsClick,
                    modifier = Modifier.align(Alignment.Center)
                )
            }

            // gallery and shutter button
            Row(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .fillMaxWidth()
                    .padding(
                        horizontal = 24.dp,
                        vertical = 24.dp
                    ),
                verticalAlignment = Alignment.CenterVertically
            )
            {
                Box(
                    Modifier.weight(1f),
                    contentAlignment = Alignment.CenterStart
                )
                {
                    IconButton(
                        onClick = onGalleryClick
                    )
                    {
                        Icon(
                            painter = painterResource(R.drawable.ic_gallery),
                            contentDescription = "open gallery",
                            tint = Color.White
                        )
                    }
                }

                ShutterButton(
                    enabled = hasCameraPermission && !isCapturing,
                    onClick = onShutterClick
                )

                Box(Modifier.weight(1f))
            }
        }

        TextOnlyButton(
            text = "직접 입력할래요",
            onClick = onManualAddClick,
            modifier = Modifier
                .fillMaxWidth(),
            textColor = DeepGreen
        )
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
            .clip(CircleShape)
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