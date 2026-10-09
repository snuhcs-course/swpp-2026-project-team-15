// AI-generated initial ingredient-entry layout with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
package com.example.mylittlechef.ui.fridge.components

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
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
import com.example.mylittlechef.ui.components.TitleText

// back button
// title text
@Composable
fun AddFlowHeader(
    onBackClick: () -> Unit,
    modifier: Modifier = Modifier,
    title: String? = null
)
{
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

        if (title != null) {
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
    }
}

// add flow header
// content
// bottom content (button)
@Composable
fun AddFlowScaffold(
    onBackClick: () -> Unit,
    modifier: Modifier = Modifier,
    title: String? = null,
    bottomContent: @Composable ColumnScope.() -> Unit,
    content: @Composable BoxScope.() -> Unit
)
{
    Scaffold(
        modifier = modifier.imePadding(),
        containerColor = Color.White,
        topBar = {
            AddFlowHeader(
                onBackClick = onBackClick,
                title = title
            )
        },
        bottomBar = {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .navigationBarsPadding()
                    .padding(bottom = 16.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                content = bottomContent
            )
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
