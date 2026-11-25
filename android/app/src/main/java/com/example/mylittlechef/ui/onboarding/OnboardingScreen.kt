// Nickname/pantry-only onboarding assisted by Codex, 2026-11-25; human review pending.
// UX2 layout/lifecycle changes assisted by Codex, 2026-11-19; human review pending.
// Onboarding scaffold adapted and reviewed by Ahyoon Choi from an earlier Claude draft.
// Responsive controls updated with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui.onboarding

import androidx.compose.animation.Crossfade
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.R
import com.example.mylittlechef.model.Preset
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.UserViewModel

@Composable
fun OnboardingScreen(user: UserViewModel, fridge: FridgeViewModel, onFinish: () -> Unit) {
    var stepIndex by rememberSaveable { mutableStateOf(1) }
    var selectedPantryItems by rememberSaveable { mutableStateOf(emptyList<String>()) }
    Crossfade(targetState=stepIndex, animationSpec=tween(160), label="onboarding-step") { step ->
    when (step) {
        1 -> OnboardingNickname(user, {stepIndex=4})
        // Retain saved step IDs; old utensil/allergy drafts now continue at pantry.
        2, 3, 4 -> OnboardingPantry(selectedPantryItems, { selectedPantryItems = it }, {stepIndex=5}, {stepIndex=1})
        else -> OnboardingDone(user, {
            fridge.updatePantryItems(selectedPantryItems, onSaved = onFinish)
        }, fridge.pantryError)
    }
    }
}

@Composable
fun OnboardingNickname(user: UserViewModel, onNext: () -> Unit) {
    var nickname by rememberSaveable { mutableStateOf(user.nickname) }
    OnboardingScaffold(
        backActive = false, jumpActive = false, onBackClick = {},
        onClick = { user.updateNickname(nickname); onNext() }, onJumpClick = {},
        centerForm = true, title = "반가워요!\n어떻게 불러드릴까요?", buttonText = "다음",
        buttonColor = MaterialTheme.colorScheme.primary,
        buttonTextColor = MaterialTheme.colorScheme.onPrimary
    ) {
        OutlinedTextField(
            value = nickname, onValueChange = { nickname = it },
            modifier = Modifier.fillMaxWidth(), label = { Text("별명") }, singleLine = true,
            trailingIcon = {
                if(nickname.isNotEmpty()) IconButton(onClick = { nickname = "" }) {
                    Icon(painterResource(R.drawable.ic_ui_close), "별명 지우기")
                }
            }
        )
    }
}

@Composable
fun OnboardingUtensil(user: UserViewModel, onNext: () -> Unit, onBack: () -> Unit) {
    var utensils by rememberSaveable { mutableStateOf(user.utensils) }
    OnboardingScaffold(
        backActive = true, jumpActive = true, onBackClick = onBack,
        onClick = { user.updateUtensils(utensils); onNext() }, onJumpClick = onNext,
        title = "집에 어떤 조리 도구가 있나요?", buttonText = "다음",
        buttonColor = MaterialTheme.colorScheme.primary,
        buttonTextColor = MaterialTheme.colorScheme.onPrimary
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text("사용할 수 있는 조리 도구를 골라주세요.", style = MaterialTheme.typography.bodyMedium)
            OnboardingChoiceGrid(Preset.utensils, utensils, { utensils = it })
        }
    }
}

@Composable
fun OnboardingAllergy(user: UserViewModel, onNext: () -> Unit, onBack: () -> Unit) {
    var allergies by rememberSaveable { mutableStateOf(user.allergies) }
    OnboardingScaffold(
        backActive = true, jumpActive = true, onBackClick = onBack,
        onClick = { user.updateAllergies(allergies); onNext() }, onJumpClick = onNext,
        title = "알레르기 정보를 알려주세요", buttonText = "다음",
        buttonColor = MaterialTheme.colorScheme.primary,
        buttonTextColor = MaterialTheme.colorScheme.onPrimary
    ) {
        Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Text(
                "정보를 기록해 두어요. 추천에 자동으로 제외되지 않으니 레시피의 재료를 직접 확인해 주세요.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
            OnboardingChoiceGrid(Preset.allergies, allergies, { allergies = it })
        }
    }
}

@Composable
fun OnboardingDone(user: UserViewModel, onNext: () -> Unit, saveError: String? = null) {
    OnboardingScaffold(
        backActive = false, jumpActive = false, onBackClick = {}, onClick = onNext,
        onJumpClick = {}, title = "${user.nickname} 님,\n이제 시작할 준비가 됐어요",
        buttonText = "시작하기", buttonColor = MaterialTheme.colorScheme.primary,
        buttonTextColor = MaterialTheme.colorScheme.onPrimary
    ) {
        Text(
            saveError ?: "입력한 정보는 언제든지 수정할 수 있어요",
            style = MaterialTheme.typography.bodyMedium,
            color = if (saveError != null) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant
        )
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
    centerForm: Boolean = false,
    content: @Composable BoxScope.() -> Unit
) {
    Scaffold(
        modifier = modifier.imePadding(),
        containerColor = MaterialTheme.colorScheme.background,
        contentColor = MaterialTheme.colorScheme.onBackground,
        topBar = {
            Box(Modifier.fillMaxWidth().statusBarsPadding().height(48.dp)) {
                if (backActive) IconButton(onBackClick, Modifier.size(48.dp)) {
                    Icon(painterResource(R.drawable.ic_back), "뒤로", tint = MaterialTheme.colorScheme.onBackground)
                }
            }
        },
        bottomBar = {
            Column(
                Modifier.fillMaxWidth().navigationBarsPadding().padding(horizontal = 20.dp, vertical = 8.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                Button(
                    onClick = onClick,
                    modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = buttonColor, contentColor = buttonTextColor)
                ) { Text(buttonText) }
                if (jumpActive) TextButton(
                    onClick = onJumpClick, modifier = Modifier.fillMaxWidth().heightIn(min = 48.dp)
                ) { Text("건너뛰기") }
            }
        }
    ) { insets ->
        BoxWithConstraints(Modifier.padding(insets).fillMaxSize()) {
            val availableHeight=maxHeight
            // Bottom alignment brings short forms into thumb reach; overflow remains scrollable.
            Column(
                Modifier.fillMaxWidth().verticalScroll(rememberScrollState())
                    .heightIn(min = maxHeight).padding(horizontal = 20.dp, vertical = 8.dp),
                verticalArrangement = if (centerForm) Arrangement.Center else Arrangement.Bottom
            ) {
                if (centerForm) Spacer(Modifier.height(availableHeight * .22f))
                if (!title.isNullOrBlank()) {
                    Text(title, style = MaterialTheme.typography.titleLarge,
                        color = MaterialTheme.colorScheme.onBackground)
                    Spacer(Modifier.height(12.dp))
                }
                Box(Modifier.fillMaxWidth(), content = content)
                Spacer(Modifier.height(if (centerForm) 0.dp else 12.dp))
            }
        }
    }
}
