package com.example.mylittlechef.ui.onboarding

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment

import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.ui.components.BackButton
import com.example.mylittlechef.ui.components.NormalButton
import com.example.mylittlechef.ui.components.SubtitleText
import com.example.mylittlechef.ui.components.TextOnlyButton

import com.example.mylittlechef.ui.components.TitleText

import com.example.mylittlechef.ui.theme.GreenGray
import com.example.mylittlechef.ui.theme.DeepGreen

@Composable
fun OnboardingScreen(
    onFinish: () -> Unit,
    modifier: Modifier = Modifier
) {
    var nickname by rememberSaveable { mutableStateOf("") }
    var tools by rememberSaveable { mutableStateOf<List<String>>(emptyList()) }
    var allergies by rememberSaveable { mutableStateOf<List<String>>(emptyList()) }

    var currentStep by remember { mutableIntStateOf(1) }
    val onNext = {
        currentStep++;
        Unit
    }
    val onBack = {
        currentStep--;
        Unit
    }

    when (currentStep) {
        1 -> OnboardingNickname(
            modifier = modifier,
            onNext = onNext,
            nickname = nickname,
            onNicknameChanged = { nickname = it }
        )
        2 -> OnboardingTool(
            modifier,
            onNext = onNext,
            onBack = onBack,
            tools = tools,
            onToolsChanged = { tools = it }
        )
        3 -> OnboardingAllergy(
            modifier,
            onNext = onNext,
            onBack = onBack,
            allergies = allergies,
            onAllergiesChanged = { allergies = it }
        )
        4 -> OnboardingDone(
            modifier,
            onNext = onFinish,
            nickname = nickname,
            tools = tools,
            allergies = allergies
        )
    }
}

@Composable
fun OnboardingNickname(
    modifier: Modifier = Modifier,
    onNext: () -> Unit,
    nickname: String,
    onNicknameChanged: (String) -> Unit
)
{
    Column(
        modifier = modifier
    )
    {
        TitleText(
            text = "환영해요!\n어떻게 불러드릴까요?",
            modifier = Modifier
                .padding(top = 100.dp),
            textAlign = TextAlign.Left,
            color = Color.Black
        )

        Spacer(Modifier.weight(1f))

        NormalButton(
            text = "다음",
            modifier = Modifier
                .align(Alignment.CenterHorizontally)
                .padding(bottom = 200.dp),
            buttonColor = GreenGray,
            textColor = Color.Black,
            onClick = onNext
        )
    }
}

@Composable
fun OnboardingTool(
    modifier: Modifier = Modifier,
    onNext: () -> Unit,
    onBack: () -> Unit,
    tools: List<String>,
    onToolsChanged: (List<String>) -> Unit
)
{
    Column(
        modifier = modifier
    )
    {
        BackButton(
            modifier = Modifier,
            onClick = onBack
        )

        TitleText(
            text = "집에 어떤 조리 도구가\n있나요?",
            modifier = Modifier
                .padding(top = 100.dp),
            textAlign = TextAlign.Left,
            color = Color.Black
        )

        SubtitleText(
            text = "주방 사정에 딱 맞는 레시피만 골라 드릴게요",
            modifier = Modifier,
            textAlign = TextAlign.Left,
            color = Color.Black
        )

        Spacer(Modifier.weight(1f))

        NormalButton(
            text = "다음",
            modifier = Modifier
                .align(Alignment.CenterHorizontally)
                .padding(bottom = 200.dp),
            buttonColor = GreenGray,
            textColor = Color.Black,
            onClick = onNext
        )

        TextOnlyButton(
            text = "건너뛰기",
            modifier = Modifier
                .align(Alignment.CenterHorizontally),
            textColor = Color.Black,
            onClick = onNext
        )
    }
}

@Composable
fun OnboardingAllergy(
    modifier: Modifier = Modifier,
    onNext: () -> Unit,
    onBack: () -> Unit,
    allergies: List<String>,
    onAllergiesChanged: (List<String>) -> Unit
)
{
    Column(
        modifier = modifier
    )
    {
        BackButton(
            modifier = Modifier,
            onClick = onBack
        )

        TitleText(
            text = "알레르기 정보를\n알려주세요",
            modifier = Modifier
                .padding(top = 100.dp),
            textAlign = TextAlign.Left,
            color = Color.Black
        )

        SubtitleText(
            text = "해당하는 재료는 빼고 레시피를 추천해 드릴게요",
            modifier = Modifier,
            textAlign = TextAlign.Left,
            color = Color.Black
        )

        Spacer(Modifier.weight(1f))

        NormalButton(
            text = "다음",
            modifier = Modifier
                .align(Alignment.CenterHorizontally)
                .padding(bottom = 200.dp),
            buttonColor = GreenGray,
            textColor = Color.Black,
            onClick = onNext
        )

        TextOnlyButton(
            text = "건너뛰기",
            modifier = Modifier
                .align(Alignment.CenterHorizontally),
            textColor = Color.Black,
            onClick = onNext
        )
    }
}

@Composable
fun OnboardingDone(
    modifier: Modifier = Modifier,
    onNext: () -> Unit,
    nickname: String,
    tools: List<String>,
    allergies: List<String>
)
{
    Column(
        modifier = modifier
    )
    {
        TitleText(
            text = "${nickname}님,\n이제 시작할 준비가 됐어요",
            modifier = Modifier
                .padding(top = 100.dp),
            textAlign = TextAlign.Center,
            color = Color.Black
        )

        SubtitleText(
            text = "입력한 정보는 언제든지 수정할 수 있어요",
            modifier = Modifier,
            textAlign = TextAlign.Center,
            color = Color.Black
        )

        NormalButton(
            text = "시작하기",
            modifier = Modifier
                .align(Alignment.CenterHorizontally)
                .padding(bottom = 200.dp),
            buttonColor = DeepGreen,
            textColor = Color.White,
            onClick = onNext
        )
    }
}

