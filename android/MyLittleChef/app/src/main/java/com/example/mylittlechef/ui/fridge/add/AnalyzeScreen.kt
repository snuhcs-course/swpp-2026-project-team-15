// AI-generated initial analysis-screen scaffold with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
package com.example.mylittlechef.ui.fridge.add

import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Preset
import com.example.mylittlechef.ui.components.SubtitleText
import com.example.mylittlechef.ui.components.NormalButton
import com.example.mylittlechef.ui.components.SubtitleText
import com.example.mylittlechef.ui.components.TextOnlyButton
import com.example.mylittlechef.ui.components.TitleText
import com.example.mylittlechef.ui.fridge.components.AddFlowScaffold
import com.example.mylittlechef.ui.fridge.components.EditableIngredientList
import com.example.mylittlechef.ui.fridge.components.IngredientEditorState
import com.example.mylittlechef.ui.fridge.components.rememberIngredientEditorState
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.ui.theme.Gray
import com.example.mylittlechef.ui.theme.GreenGray
import com.example.mylittlechef.ui.theme.MyLittleChefTheme
import com.example.mylittlechef.viewmodel.FridgeViewModel
import kotlinx.coroutines.delay
import kotlin.time.Duration.Companion.milliseconds
import androidx.core.net.toUri

sealed interface AnalyzeUiState {
    data object Loading : AnalyzeUiState
    data object Failed : AnalyzeUiState
    data object Success : AnalyzeUiState
}

@Composable
fun AnalyzeScreen(
    modifier: Modifier = Modifier,
    fridge: FridgeViewModel,
    onBackClick: () -> Unit,
    onManualClick: () -> Unit,
    onRetakeClick: () -> Unit,
    onSaveClick: () -> Unit,
    imageUri: String? = null
)
{
    val editor = rememberIngredientEditorState()
    var uiState by remember { mutableStateOf<AnalyzeUiState>(AnalyzeUiState.Loading) }

    LaunchedEffect(Unit) {
        delay(2000.milliseconds)
        editor.replaceAll(Preset.analyzeResult)
        uiState = AnalyzeUiState.Success
    }

    AnalyzeContent(
        fridge = fridge,
        uiState = uiState,
        editor = editor,
        onBackClick = onBackClick,
        onManualClick = onManualClick,
        onRetakeClick = onRetakeClick,
        onSaveClick = onSaveClick,
        imageUri = imageUri,
        modifier = modifier
    )
}

@Composable
private fun AnalyzeContent(
    modifier: Modifier = Modifier,
    fridge: FridgeViewModel,
    uiState: AnalyzeUiState,
    editor: IngredientEditorState,
    onBackClick: () -> Unit,
    onManualClick: () -> Unit,
    onRetakeClick: () -> Unit,
    onSaveClick: () -> Unit,
    imageUri: String? = null
) {
    AddFlowScaffold(
        onBackClick = onBackClick,
        modifier = modifier,
        title = when (uiState) {
            AnalyzeUiState.Loading -> "AI가 재료를 찾고 있어요..."
            AnalyzeUiState.Failed -> ""
            AnalyzeUiState.Success -> "AI가 재료를 찾았어요"
        },
        bottomContent = {
            when (uiState) {
                AnalyzeUiState.Loading -> NormalButton(
                    text = "인식 중...",
                    buttonColor = GreenGray,
                    textColor = Color.Black,
                    onClick = {}
                )
                AnalyzeUiState.Failed -> NormalButton(
                    text = "직접 입력",
                    buttonColor = DeepGreen,
                    textColor = Color.White,
                    onClick = onManualClick
                )
                AnalyzeUiState.Success -> NormalButton(
                    text = "냉장고에 반영",
                    buttonColor = DeepGreen,
                    textColor = Color.White,
                    onClick = {
                        editor.finishEdit()
                        if (editor.ingredients.isNotEmpty()) {
                            fridge.addIngredients(editor.ingredients)
                        }
                        onSaveClick()
                    }
                )
            }
            TextOnlyButton(
                text = "다시 찍기",
                textColor = Color.Black,
                onClick = onRetakeClick
            )
        }
    ) {
        when (uiState) {
            AnalyzeUiState.Loading -> CapturedPhoto(imageUri, Modifier.align(Alignment.Center))
            AnalyzeUiState.Failed -> FailedMessage(Modifier.align(Alignment.Center))
            AnalyzeUiState.Success -> EditableIngredientList(
                editor = editor,
                modifier = Modifier.fillMaxSize()
            )
        }
    }
}

@Composable
private fun CapturedPhoto(
    imageUri: String?,
    modifier: Modifier = Modifier
)
{
    val frame = modifier
        .fillMaxWidth(0.7f)
        .aspectRatio(150f / 160f)
        .clip(RoundedCornerShape(4.dp))
        .background(Gray)

    if (imageUri != null) {
        AsyncImage(
            model = imageUri.toUri(),
            contentDescription = "촬영한 사진",
            modifier = frame,
            contentScale = ContentScale.Crop
        )
    } else {
        Box(frame)
    }
}

@Composable
private fun FailedMessage(modifier: Modifier = Modifier) {
    Column(
        modifier = modifier,
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        TitleText(
            text = "앗, 재료를 못 찾았어요",
            color = MaterialTheme.colorScheme.onSurface,
            textAlign = TextAlign.Center
        )
        Spacer(Modifier.height(12.dp))
        SubtitleText(
            text = "직접 입력하면 바로 추가할 수 있어요",
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center
        )
    }
}
