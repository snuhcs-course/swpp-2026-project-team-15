// Real entry sheets assisted by Codex, 2026-11-19; human review pending.
package com.example.mylittlechef.ui.fridge.add

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp

@Stable
class EntrySheetControls {
    var busy by mutableStateOf(false)
    var draft by mutableStateOf(false)
    var requestClose: () -> Unit = {}
    var complete: () -> Unit = {}
}
val LocalEntrySheet = staticCompositionLocalOf<EntrySheetControls?> { null }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun EntrySheet(onClose: () -> Unit, heightFraction: Float = .82f, content: @Composable () -> Unit) {
    val controls = remember { EntrySheetControls() }
    var confirmClose by rememberSaveable { mutableStateOf(false) }
    var closing by rememberSaveable { mutableStateOf(false) }
    fun close() { if (!controls.busy && !closing) { if (controls.draft) confirmClose=true else closing=true } }
    SideEffect { controls.requestClose = { close() }; controls.complete = { closing=true } }
    val state = rememberModalBottomSheetState(skipPartiallyExpanded=true, confirmValueChange={ target ->
        if(target==SheetValue.Hidden && !closing && (controls.busy || controls.draft)) {
            if(!controls.busy) confirmClose=true
            false
        } else true
    })
    val density=LocalDensity.current
    val imeOpen=WindowInsets.ime.getBottom(density)>0
    LaunchedEffect(imeOpen) { if(imeOpen && !closing) state.expand() }
    // Save completion survives rotation during the exit animation without a second save.
    LaunchedEffect(closing) { if(closing) { state.hide(); onClose() } }
    ModalBottomSheet(onDismissRequest={close()}, sheetState=state,
        containerColor=MaterialTheme.colorScheme.background,
        modifier=Modifier.testTag("ingredient-entry-sheet")) {
        BackHandler { close() }
        CompositionLocalProvider(LocalEntrySheet provides controls) {
            Box(Modifier.fillMaxWidth().fillMaxHeight(if(imeOpen) .94f else heightFraction).imePadding()) { content() }
        }
    }
    if(confirmClose) AlertDialog(onDismissRequest={confirmClose=false},
        title={Text("입력한 내용을 닫을까요?")}, text={Text("아직 저장하지 않은 재료는 사라져요.")},
        confirmButton={TextButton(onClick={confirmClose=false;closing=true},enabled=!controls.busy,
            modifier=Modifier.testTag("discard-entry-draft")){Text("닫기")}},
        dismissButton={TextButton(onClick={confirmClose=false}){Text("계속 입력")}})
}
