package com.example.mylittlechef.ui.profile

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.material3.Scaffold
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.ui.components.BackButton
import com.example.mylittlechef.ui.components.NormalButton
import com.example.mylittlechef.ui.components.TitleText
import com.example.mylittlechef.ui.theme.GreenGray

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
                        bottom = 16.dp
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