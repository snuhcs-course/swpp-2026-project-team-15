package com.example.mylittlechef.ui.profile

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.ui.components.BackButton
import com.example.mylittlechef.ui.components.NormalButton
import com.example.mylittlechef.ui.components.TitleText
import com.example.mylittlechef.ui.theme.GreenGray
import com.example.mylittlechef.viewmodel.UserViewModel

import com.example.mylittlechef.R
import com.example.mylittlechef.model.Preset
import com.example.mylittlechef.ui.components.ToggleButton
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.ui.theme.Gray

@Composable
fun EditNicknameScreen(
    user: UserViewModel,
    onBackClick: () -> Unit,
    onSaveClick: () -> Unit
)
{
    var nickname by remember { mutableStateOf(user.nickname) }

    EditProfileScaffold(
        onBackClick = onBackClick,
        onSaveClick = {
            user.updateNickname(nickname)
            onSaveClick()
        },
        title = "별명 설정"
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
            verticalArrangement = Arrangement.spacedBy(16.dp)
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
fun EditUtensilScreen(
    user: UserViewModel,
    onBackClick: () -> Unit,
    onSaveClick: () -> Unit
)
{
    var utensils by remember { mutableStateOf(user.utensils) }

    EditProfileScaffold(
        onBackClick = onBackClick,
        onSaveClick = {
            user.updateUtensils(utensils)
            onSaveClick()
        },
        title = "조리 도구 설정"
    )
    {
        FlowRow(
            modifier = Modifier
                .fillMaxWidth()
                .padding(
                    start = 30.dp,
                    end = 30.dp,
                    top = 50.dp
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
                        }
                        else {
                            utensils += utensil
                        }
                    }
                )
            }
        }
    }
}

@Composable
fun EditAllergyScreen(
    user: UserViewModel,
    onBackClick: () -> Unit,
    onSaveClick: () -> Unit
)
{
    var allergies by remember { mutableStateOf(user.allergies) }

    EditProfileScaffold(
        onBackClick = onBackClick,
        onSaveClick = {
            user.updateAllergies(allergies)
            onSaveClick()
        },
        title = "알레르기 설정"
    )
    {
        FlowRow(
            modifier = Modifier
                .fillMaxWidth()
                .padding(
                    start = 30.dp,
                    end = 30.dp,
                    top = 50.dp
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

// back button
// title text
// content
// save button
@Composable
fun EditProfileScaffold(
    onBackClick: () -> Unit,
    onSaveClick: () -> Unit,
    modifier: Modifier = Modifier,
    title: String,
    content: @Composable BoxScope.() -> Unit
)
{
    Scaffold(
        modifier = modifier.imePadding(),
        containerColor = Color.White,
        topBar = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .statusBarsPadding()
                    .padding(
                        bottom = 16.dp
                    )
            )
            {
                BackButton(
                    onClick = onBackClick
                )
                TitleText(
                    text = title,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(
                            horizontal = 24.dp
                        ),
                    textAlign = TextAlign.Center,
                    color = Color.Black
                )
            }
        },
        bottomBar = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .navigationBarsPadding()
                    .padding(
                        bottom = 36.dp
                    ),
                horizontalAlignment = Alignment.CenterHorizontally
            )
            {
                NormalButton(
                    text = "저장",
                    buttonColor = GreenGray,
                    textColor = Color.Black,
                    onClick = onSaveClick
                )
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