// UAT stage 1 assisted by Codex, 2026-11-24; human review pending.
package com.example.mylittlechef.ui.fridge
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import com.example.mylittlechef.viewmodel.FridgeViewModel
/** Fixed outside the list; rendered inside the modal window while open. */
@Composable fun AdditionFeedback(fridge: FridgeViewModel, modifier: Modifier=Modifier) {
 fridge.additionNotice?.let { notice ->
 Snackbar(modifier.testTag("suggestion-feedback"),actionOnNewLine=true,
 action={notice.action?.let {label ->TextButton(onClick={fridge.actOnAddition(notice.id)},enabled=!fridge.isSavingSuggestion,modifier=Modifier.testTag("suggestion-feedback-action")) {Text(if(fridge.isSavingSuggestion) "저장 중…" else label,color=MaterialTheme.colorScheme.inversePrimary)}}},
 dismissAction={TextButton(onClick={fridge.dismissAddition(notice.id)},enabled=!fridge.isSavingSuggestion) {Text("닫기",color=MaterialTheme.colorScheme.inverseOnSurface)}}) {Text(notice.message)}
 }
}
