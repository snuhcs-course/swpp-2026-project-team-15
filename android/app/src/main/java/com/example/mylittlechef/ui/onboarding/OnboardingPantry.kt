// AI-assisted with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
package com.example.mylittlechef.ui.onboarding

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.model.Preset
import com.example.mylittlechef.ui.components.SubtitleText
import com.example.mylittlechef.ui.components.ToggleButton
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.ui.theme.Gray
import com.example.mylittlechef.ui.theme.GreenGray

@Composable
fun OnboardingPantry(
    selected: List<String>,
    onSelectedChange: (List<String>) -> Unit,
    onNext: () -> Unit,
    onBack: () -> Unit
) {
    OnboardingScaffold(
        backActive = true,
        jumpActive = true,
        onBackClick = onBack,
        onClick = onNext,
        onJumpClick = onNext,
        title = "집에 있는 기본 재료와\n조미료를 골라주세요",
        buttonText = "다음",
        buttonColor = GreenGray,
        buttonTextColor = Color.Black
    ) {
        PantrySelectionContent(selected, onSelectedChange)
    }
}

@Composable
fun PantrySelectionContent(
    selected: List<String>,
    onSelectedChange: (List<String>) -> Unit
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(start = 30.dp, end = 30.dp, top = 16.dp, bottom = 20.dp)
    ) {
        SubtitleText(
            text = "사진에 잘 안 보이는 재료를 한 번에 등록해요. 없는 것은 선택하지 않아도 돼요.",
            textAlign = TextAlign.Left,
            color = Color.Black
        )
        Spacer(Modifier.height(20.dp))
        PantryChoices("조미료", Preset.pantrySeasonings, selected, onSelectedChange)
        Spacer(Modifier.height(24.dp))
        PantryChoices("기본 재료", Preset.pantryBasics, selected, onSelectedChange)
    }
}

@Composable
private fun PantryChoices(
    title: String,
    choices: List<String>,
    selected: List<String>,
    onSelectedChange: (List<String>) -> Unit
) {
    Text(text = title, style = MaterialTheme.typography.labelMedium, color = Color.Black)
    FlowRow(
        modifier = Modifier.fillMaxWidth().padding(top = 12.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        choices.forEach { item ->
            ToggleButton(
                text = item,
                selected = item in selected,
                buttonColorOn = DeepGreen,
                buttonColorOff = Gray,
                textColorOn = Color.White,
                textColorOff = Color.Black,
                onClick = {
                    onSelectedChange(if (item in selected) selected - item else selected + item)
                }
            )
        }
    }
}
