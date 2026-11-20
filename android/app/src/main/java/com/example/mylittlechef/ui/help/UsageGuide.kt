// AI-assisted HE visual help, 2026-11-09; manual review pending.
package com.example.mylittlechef.ui.help

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.R
import com.example.mylittlechef.data.local.UsageGuideRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

@Composable
fun FirstUseGuide(repository: UsageGuideRepository, enabled: Boolean) {
    val seen by repository.seenVersion.collectAsState(initial = null)
    val scope = rememberCoroutineScope()
    var saving by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    if (enabled && seen != null && seen!! < UsageGuideRepository.CURRENT_VERSION) {
        UsageGuideDialog(saving = saving, error = error, onClose = {
            if (!saving) {
                saving = true
                scope.launch {
                    try { repository.markSeen(); error = null }
                    catch (cancelled: CancellationException) { throw cancelled }
                    catch (_: Exception) { error = "안내 확인을 저장하지 못했어요. 다시 시도해 주세요." }
                    finally { saving = false }
                }
            }
        })
    }
}

@Composable
fun UsageGuideDialog(onClose: () -> Unit, saving: Boolean = false, error: String? = null) {
    AlertDialog(
        modifier = Modifier.testTag("usage-guide"),
        onDismissRequest = { if (!saving) onClose() },
        title = { Text("사용 안내") },
        text = {
            Column(Modifier.heightIn(max = 420.dp).verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(20.dp)) {
                GuideItem(R.drawable.ic_edit, "1. 재료 추가", "냉장고에서 직접 입력하거나 사진으로 재료를 찾아보세요. 여러 재료를 함께 추가할 수 있어요.")
                GuideItem(R.drawable.ic_gallery, "2. 확인하고 저장", "인식 결과를 확인하고 이름을 수정해 주세요. 실수로 지운 항목은 실행 취소로 되돌릴 수 있어요.")
                GuideItem(R.drawable.ic_recipe, "3. AI 제안", "원하는 요리의 상세에서 AI 제안을 요청해 보세요. 재료·조리법을 원본과 비교하고 알레르기를 확인해 주세요.")
                Text("이 안내는 내 정보에서 다시 볼 수 있어요.", style = MaterialTheme.typography.bodySmall)
                error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            }
        },
        confirmButton = {
            TextButton(onClick = onClose, enabled = !saving, modifier = Modifier.testTag("close-usage-guide")) {
                Text(if (saving) "저장 중" else if (error != null) "다시 시도" else "확인")
            }
        }
    )
}

@Composable
private fun GuideItem(icon: Int, title: String, body: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), verticalAlignment = Alignment.Top) {
        Icon(painterResource(icon), contentDescription = null, tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(32.dp))
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleSmall)
            Spacer(Modifier.height(6.dp))
            Text(body, style = MaterialTheme.typography.bodyMedium)
        }
    }
}
