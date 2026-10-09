// AI-generated initial onboarding scaffold with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
package com.example.mylittlechef.ui.onboarding

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text

import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment

import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.R
import com.example.mylittlechef.model.Preset
import com.example.mylittlechef.ui.components.BackButton
import com.example.mylittlechef.ui.components.NormalButton
import com.example.mylittlechef.ui.components.SubtitleText
import com.example.mylittlechef.ui.components.TextOnlyButton

import com.example.mylittlechef.ui.components.TitleText
import com.example.mylittlechef.ui.components.ToggleButton

import com.example.mylittlechef.ui.theme.GreenGray
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.ui.theme.Gray
import com.example.mylittlechef.viewmodel.UserViewModel

@Composable
fun OnboardingScreen(
    user: UserViewModel,
    onFinish: () -> Unit
)
{
    var stepIndex by remember { mutableStateOf(1) }
    val onNext = { stepIndex += 1 }
    val onBack = { stepIndex -= 1 }

    when (stepIndex) {
        1 -> OnboardingNickname(
            user = user,
            onNext = onNext
        )
        2 -> OnboardingUtensil(
            user = user,
            onNext = onNext,
            onBack = onBack
        )
        3 -> OnboardingAllergy(
            user = user,
            onNext = onNext,
            onBack = onBack
        )
        4 -> OnboardingDone(
            user = user,
            onNext = onFinish,
        )
    }
}

@Composable
fun OnboardingNickname(
    user: UserViewModel,
    onNext: () -> Unit
)
{
    var nickname by remember { mutableStateOf(user.nickname) }

    OnboardingScaffold(
        backActive = false,
        jumpActive = false,
        onBackClick = {},
        onClick = {
            user.updateNickname(nickname)
            onNext()
        },
        onJumpClick = {},
        title = "환영해요!\n어떻게 불러드릴까요?",
        buttonText = "다음",
        buttonColor = GreenGray,
        buttonTextColor = Color.Black
    )
    {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(
                    start = 30.dp,
                    end = 30.dp,
                    top = 50.dp
                ),
        )
        {
            Text(
                text = "별명",
                style = MaterialTheme.typography.labelMedium,
                color = Color.Black,
                textAlign = TextAlign.Left,
                modifier = Modifier
                    .fillMaxWidth()
            )

            OutlinedTextField(
                value = nickname,
                onValueChange = {
                    nickname = it
                },
                modifier = Modifier
                    .fillMaxWidth(),
                trailingIcon = {
                    Icon(
                        painter = painterResource(R.drawable.ic_xcircle),
                        contentDescription = "clear nickname",
                        tint = Color.Unspecified
                    )
                }
            )
        }
    }
}

@Composable
fun OnboardingUtensil(
    user: UserViewModel,
    onNext: () -> Unit,
    onBack: () -> Unit
)
{
    var utensils by remember { mutableStateOf(user.utensils) }

    OnboardingScaffold(
        backActive = true,
        jumpActive = true,
        onBackClick = onBack,
        onClick = {
            user.updateUtensils(utensils)
            onNext()
        },
        onJumpClick = onNext,
        title = "집에 어떤 조리 도구가\n있나요?",
        buttonText = "다음",
        buttonColor = GreenGray,
        buttonTextColor = Color.Black
    )
    {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(
                    start = 30.dp,
                    end = 30.dp,
                    top = 16.dp
                )
        )
        {
            SubtitleText(
                text = "주방 사정에 딱 맞는 레시피만 골라 드릴게요",
                textAlign = TextAlign.Left,
                color = Color.Black
            )
            FlowRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(
                        top = 20.dp
                    ),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            )
            {
                Preset.utensils.forEach { utensil ->
                    ToggleButton(
                        text = utensil,
                        selected = utensil in utensils,
                        buttonColorOn = DeepGreen,
                        buttonColorOff = Gray,
                        textColorOn = Color.White,
                        textColorOff = Color.Black,
                        onClick = {
                            if (utensil in utensils) {
                                utensils -= utensil
                            } else {
                                utensils += utensil
                            }
                        }
                    )
                }
            }
        }
    }
}

@Composable
fun OnboardingAllergy(
    user: UserViewModel,
    onNext: () -> Unit,
    onBack: () -> Unit
)
{
    var allergies by remember { mutableStateOf(user.allergies) }

    OnboardingScaffold(
        backActive = true,
        jumpActive = true,
        onBackClick = onBack,
        onClick = {
            user.updateAllergies(allergies)
            onNext()
        },
        onJumpClick = onNext,
        title = "알레르기 정보를\n알려주세요",
        buttonText = "다음",
        buttonColor = GreenGray,
        buttonTextColor = Color.Black
    )
    {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(
                    start = 30.dp,
                    end = 30.dp,
                    top = 16.dp
                )
        )
        {
            SubtitleText(
                text = "해당하는 재료는 빼고 레시피를 추천해 드릴게요",
                textAlign = TextAlign.Left,
                color = Color.Black
            )
            FlowRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(
                        top = 20.dp
                    ),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp)
            )
            {
                Preset.allergies.forEach { allergy ->
                    ToggleButton(
                        text = allergy,
                        selected = allergy in allergies,
                        buttonColorOn = DeepGreen,
                        buttonColorOff = Gray,
                        textColorOn = Color.White,
                        textColorOff = Color.Black,
                        onClick = {
                            if (allergy in allergies) {
                                allergies -= allergy
                            }
                            else {
                                allergies += allergy
                            }
                        }
                    )
                }
            }
        }

    }
}

@Composable
fun OnboardingDone(
    user: UserViewModel,
    onNext: () -> Unit
)
{
    OnboardingScaffold(
        backActive = false,
        jumpActive = false,
        onBackClick = { },
        onClick = onNext,
        onJumpClick = {},
        title = "",
        buttonText = "시작하기",
        buttonColor = DeepGreen,
        buttonTextColor = Color.White
    )
    {
        Column (
            modifier = Modifier
                .fillMaxSize(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(10.dp)

        )
        {
            TitleText(
                text = "${user.nickname} 님,\n이제 시작할 준비가 됐어요",
                textAlign = TextAlign.Center,
                color = Color.Black
            )

            SubtitleText(
                text = "입력한 정보는 언제든지 수정할 수 있어요",
                textAlign = TextAlign.Center,
                color = Color.Black
            )

        }
    }
}

@Composable
fun OnboardingScaffold(
    backActive: Boolean,
    jumpActive: Boolean,
    onBackClick: () -> Unit,
    onClick: () -> Unit,
    onJumpClick: () -> Unit,
    modifier: Modifier = Modifier,
    title: String? = null,
    buttonText: String,
    buttonColor: Color,
    buttonTextColor: Color,
    content: @Composable BoxScope.() -> Unit
)
{
    Scaffold(
        modifier = modifier.imePadding(),
        containerColor = Color.White,
        topBar = {
            Column(
                modifier = modifier
                    .fillMaxWidth()
                    .statusBarsPadding()
                    .padding(
                        bottom = 16.dp
                    )
            )
            {
                if (backActive) {
                    BackButton(
                        onClick = onBackClick
                    )
                }
                else {
                    Box(
                        modifier = Modifier.height(24.dp)
                    )
                }

                if (title != null) {
                    TitleText(
                        text = title,
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(
                                horizontal = 24.dp
                            ),
                        textAlign = TextAlign.Left,
                        color = Color.Black
                    )
                }
            }
        },
        bottomBar = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .navigationBarsPadding()
                    .padding(bottom = 16.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            )
            {
                NormalButton(
                    text = buttonText,
                    buttonColor = buttonColor,
                    textColor = buttonTextColor,
                    onClick = onClick
                )

                if (jumpActive) {
                    TextOnlyButton(
                        text = "건너뛰기",
                        textColor = Color.Black,
                        onClick = onJumpClick
                    )
                }
                else {
                    Box(
                        modifier = Modifier.height(20.dp)
                    )
                }
            }
        }
    )
    {
        innerPadding ->
        Box(
            modifier = Modifier
                .padding(innerPadding)
                .fillMaxSize(),
            content = content
        )
    }
}
