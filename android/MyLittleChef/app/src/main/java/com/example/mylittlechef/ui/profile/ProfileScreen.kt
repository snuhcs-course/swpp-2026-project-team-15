package com.example.mylittlechef.ui.profile

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
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.R
import com.example.mylittlechef.ui.components.TitleText
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.ui.theme.GreenGray

@Composable
fun ProfileScreen(
    onEditNicknameClick: () -> Unit,
    onEditToolClick: () -> Unit,
    onEditAllergyClick: () -> Unit,
    modifier: Modifier = Modifier
)
{

}

@Composable
fun ProfileContent(
    onEditNicknameClick: () -> Unit,
    onEditToolClick: () -> Unit,
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
            text = "다시 만나서 반가워요,\n가나다 님", // TODO: Color tag
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
                    .fillMaxWidth(),
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
    }
}