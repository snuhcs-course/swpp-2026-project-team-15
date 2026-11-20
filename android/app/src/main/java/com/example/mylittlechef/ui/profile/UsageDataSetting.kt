// AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.ui.profile

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.width
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.viewmodel.UsageDataViewModel

/** One wording for what is and is not sent, shared by the notice, the switch and the ⓘ dialog. */
internal object UsageDataCopy {
    const val TITLE = "사용 기록 보내기"
    const val WHAT = "베타 기간 동안 앱을 어떻게 쓰는지(누른 화면, 걸린 시간, 오류)를 이름 없이 모아 앱을 고치는 데 써요."
    const val NOT = "재료 이름, 사진, 별명은 보내지 않아요. 내 정보에서 언제든 끌 수 있어요."
}

/** Shown once, before anything is sent. */
@Composable
fun UsageDataNotice(usage: UsageDataViewModel) {
    if (!usage.showNotice) return
    AlertDialog(
        onDismissRequest = {},
        title = { Text("사용 기록 수집 안내") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(UsageDataCopy.WHAT)
                Text(UsageDataCopy.NOT)
            }
        },
        confirmButton = {
            TextButton(onClick = { usage.answerNotice(true) }, modifier = Modifier.testTag("usage-accept")) { Text("보내기") }
        },
        dismissButton = {
            TextButton(onClick = { usage.answerNotice(false) }, modifier = Modifier.testTag("usage-decline")) { Text("보내지 않기") }
        }
    )
}

@Composable
fun UsageDataSwitch(usage: UsageDataViewModel) {
    val state = usage.state ?: return
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(UsageDataCopy.TITLE, style = MaterialTheme.typography.titleMedium)
            Text(UsageDataCopy.NOT, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.width(12.dp))
        Switch(
            checked = state.enabled,
            onCheckedChange = usage::setEnabled,
            modifier = Modifier.testTag("usage-switch")
        )
    }
}
