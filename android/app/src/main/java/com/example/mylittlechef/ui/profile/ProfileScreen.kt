package com.example.mylittlechef.ui.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.R
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.ui.components.TitleText
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.ui.theme.GreenGray
import com.example.mylittlechef.viewmodel.UserViewModel

@Composable
fun ProfileScreen(
    user: UserViewModel,
    onEditNicknameClick: () -> Unit,
    onEditUtensilClick: () -> Unit,
    onEditAllergyClick: () -> Unit,
    modifier: Modifier = Modifier
)
{
    ProfileContent(
        user = user,
        onEditNicknameClick = onEditNicknameClick,
        onEditUtensilClick = onEditUtensilClick,
        onEditAllergyClick = onEditAllergyClick,
        modifier = modifier
            .background(color = Color.White)
    )
}

@Composable
fun ProfileContent(
    user: UserViewModel,
    onEditNicknameClick: () -> Unit,
    onEditUtensilClick: () -> Unit,
    onEditAllergyClick: () -> Unit,
    modifier: Modifier = Modifier
)
{
    Column(
        modifier = modifier
            .fillMaxSize()
            .padding(
                horizontal = 29.dp
            )
    )
    {
        Spacer(Modifier.height(32.dp))

        TitleText(
            text = "다시 만나서 반가워요,\n${user.nickname} 님", // TODO: Color tag
            color = Color.Black
        )

        Spacer(Modifier.height(32.dp))

        Column(
            modifier = modifier
                .fillMaxSize()
        )
        {
            ProfileItem(
                onMoreClick = onEditNicknameClick,
                title = "별명",
                contents = listOf(user.nickname)
            )

            ProfileItem(
                onMoreClick = onEditUtensilClick,
                title = "조리 도구",
                contents = if (user.utensils.isEmpty()) listOf("없음") else user.utensils
            )

            ProfileItem(
                onMoreClick = onEditAllergyClick,
                title = "알레르기",
                contents = if (user.allergies.isEmpty()) listOf("없음") else user.allergies
            )
        }

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
                    contentDescription = "more",
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