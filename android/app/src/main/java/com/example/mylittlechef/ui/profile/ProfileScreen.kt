// Retired allergy/utensil settings assisted by Codex, 2026-11-25; human review pending.
// UX2 layout/lifecycle changes assisted by Codex, 2026-11-19; human review pending.
// UI ergonomics and theme changes assisted by Codex, 2026-11-03; human review pending.
// Pantry profile row added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
package com.example.mylittlechef.ui.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.TextButton
import androidx.compose.material3.ButtonDefaults
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.testTag
import com.example.mylittlechef.viewmodel.DataResetViewModel
import com.example.mylittlechef.viewmodel.UsageDataViewModel
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import com.example.mylittlechef.ui.help.LocalSectionTour
import com.example.mylittlechef.ui.help.tourAnchor
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import com.example.mylittlechef.ui.help.UsageGuideDialog
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.R
import com.example.mylittlechef.model.Preset
import com.example.mylittlechef.ui.components.TitleText
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.ui.theme.GreenGray
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.UserViewModel
import com.example.mylittlechef.ui.theme.LocalAppearanceSettings

@Composable
fun ProfileScreen(
    user: UserViewModel,
    fridge: FridgeViewModel,
    onEditNicknameClick: () -> Unit,
    onEditUtensilClick: () -> Unit,
    onEditAllergyClick: () -> Unit,
    onEditPantryClick: () -> Unit,
    modifier: Modifier = Modifier,
    dataReset: DataResetViewModel? = null,
    onDataResetDone: () -> Unit = {},
    usageData: UsageDataViewModel? = null
)
{
    ProfileContent(
        usageData = usageData,
        user = user,
        fridge = fridge,
        onEditNicknameClick = onEditNicknameClick,
        onEditUtensilClick = onEditUtensilClick,
        onEditAllergyClick = onEditAllergyClick,
        onEditPantryClick = onEditPantryClick,
        dataReset = dataReset,
        onDataResetDone = onDataResetDone,
        modifier = modifier
            .background(color = MaterialTheme.colorScheme.background)
    )
}

@Composable
fun ProfileContent(
    user: UserViewModel,
    fridge: FridgeViewModel,
    onEditNicknameClick: () -> Unit,
    onEditUtensilClick: () -> Unit,
    onEditAllergyClick: () -> Unit,
    onEditPantryClick: () -> Unit,
    modifier: Modifier = Modifier,
    dataReset: DataResetViewModel? = null,
    onDataResetDone: () -> Unit = {},
    usageData: UsageDataViewModel? = null
)
{
    val sectionTour=LocalSectionTour.current
    var showGuide by remember { mutableStateOf(false) }
    if (showGuide) UsageGuideDialog(onClose = { showGuide = false })
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(
                horizontal = 20.dp
            )
    )
    {
        Spacer(Modifier.height(20.dp))

        Row(Modifier.fillMaxWidth(),verticalAlignment=Alignment.Top) {
            TitleText(text="내 정보",
                color=MaterialTheme.colorScheme.onBackground,modifier=Modifier.weight(1f))
            AppearancePicker()
        }
        LocalAppearanceSettings.current.error?.let { Text(it,color=MaterialTheme.colorScheme.error) }

        Spacer(Modifier.height(20.dp))

        Column(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .verticalScroll(rememberScrollState())
        )
        {
            ProfileItem(
                onMoreClick = onEditNicknameClick,
                title = "별명",
                contents = listOf(user.nickname)
            )

            val pantryOptions = Preset.pantrySeasonings + Preset.pantryBasics
            val ownedNames = fridge.ingredients.map { it.name }.toSet()
            val selectedPantry = pantryOptions.filter { it in ownedNames }
            val pantrySummary = when {
                selectedPantry.isEmpty() -> "없음"
                selectedPantry.size <= 2 -> selectedPantry.joinToString(", ")
                else -> "${selectedPantry.take(2).joinToString(", ")} 외 ${selectedPantry.size - 2}개"
            }
            ProfileItem(
                onMoreClick = onEditPantryClick,
                modifier = Modifier.tourAnchor("profile-pantry"),
                title = "기본 재료·조미료",
                contents = listOf(pantrySummary)
            )
            ProfileItem(onMoreClick = { if(sectionTour!=null) sectionTour.launch() else showGuide = true }, title = "사용 안내", contents = listOf("화면을 보며 앱 둘러보기"))

            if (usageData != null) {
                Spacer(Modifier.height(24.dp))
                UsageDataSwitch(usageData)
            }

            if (dataReset != null) {
                Spacer(Modifier.height(24.dp))
                DataResetSection(dataReset, onDataResetDone)
                Spacer(Modifier.height(32.dp))
            }
        }

    }
}

/** One wording for what a reset erases, so the row and the dialog cannot drift apart. */
internal object DataResetCopy {
    private const val ERASED = "냉장고, 프로필, 즐겨찾기, 화면 모드"
    const val SUMMARY = "${ERASED}를 지우고 처음부터 다시 시작해요."
    const val CONFIRM = "${ERASED}가 모두 지워져요. 되돌릴 수 없어요."
}

/** Bottom section of 내 정보: wipes the local data after a confirmation and starts over at the onboarding. */
@Composable
private fun DataResetSection(dataReset: DataResetViewModel, onDone: () -> Unit) {
    var confirming by rememberSaveable { mutableStateOf(false) }
    HorizontalDivider(thickness = 1.dp, color = GreenGray)
    Spacer(Modifier.height(16.dp))
    Text(text = "데이터 초기화", style = MaterialTheme.typography.titleMedium)
    Text(
        text = DataResetCopy.SUMMARY,
        style = MaterialTheme.typography.bodySmall,
        modifier = Modifier.padding(vertical = 4.dp)
    )
    dataReset.error?.let {
        Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
    }
    OutlinedButton(
        onClick = { dataReset.dismissError(); confirming = true },
        enabled = !dataReset.isResetting,
        colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error),
        modifier = Modifier.testTag("reset-data")
    ) { Text(if (dataReset.isResetting) "초기화하고 있어요" else "데이터 초기화") }
    if (confirming) {
        AlertDialog(
            onDismissRequest = { confirming = false },
            title = { Text("데이터를 초기화할까요?") },
            text = { Text(DataResetCopy.CONFIRM) },
            confirmButton = {
                TextButton(
                    modifier = Modifier.testTag("confirm-reset-data"),
                    onClick = {
                        confirming = false
                        dataReset.resetAll(onDone)
                    }
                ) { Text("초기화", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = {
                TextButton(modifier = Modifier.testTag("cancel-reset-data"), onClick = { confirming = false }) { Text("취소") }
            }
        )
    }
}

@Composable
fun ProfileItem(
    onMoreClick: () -> Unit,
    title: String,
    contents: List<String>,
    modifier: Modifier = Modifier
)
{
    Column(
        modifier = modifier
            .fillMaxWidth()
            .clickable(onClick = onMoreClick)
    )
    {
        Text(
            text = title,
            style = MaterialTheme.typography.titleMedium
        )

        Row(
            modifier = Modifier
                .fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        )
        {
            Text(
                text = contents.joinToString(", "),
                style = MaterialTheme.typography.titleSmall,
                modifier = Modifier
                    .weight(1f),
                textAlign = TextAlign.Left
            )

            IconButton(
                onClick = onMoreClick
            )
            {
                Icon(
                    painter = painterResource(R.drawable.ic_more),
                    contentDescription = "$title 수정 또는 열기",
                    tint = DeepGreen
                )
            }
        }

        HorizontalDivider(
            thickness = 1.dp,
            color = GreenGray
        )

        Spacer(Modifier.height(16.dp))
    }
}

// ─────────────────────────────────────────────
// 더미 데이터와 미리보기
// ─────────────────────────────────────────────
private val sampleUser = UserViewModel(
    nickname = "가나다",
    utensils = listOf("인덕션", "전자레인지"),
    allergies = emptyList()
)
