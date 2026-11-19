// UX2 layout/lifecycle changes assisted by Codex, 2026-11-19; human review pending.
// HE photo review assisted by Codex, 2026-11-09; manual review pending.
package com.example.mylittlechef.ui.fridge.add

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.compose.foundation.background
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.toggleable
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.core.net.toUri
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import coil3.compose.AsyncImage
import com.example.mylittlechef.data.IngredientAnalyzer
import com.example.mylittlechef.domain.PhotoAnalysisState
import com.example.mylittlechef.domain.RecognitionMode
import com.example.mylittlechef.ui.fridge.components.AddFlowScaffold
import com.example.mylittlechef.ui.fridge.components.EditableIngredientList
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.IngredientCatalogViewModel
import com.example.mylittlechef.viewmodel.PhotoAnalysisViewModel

@Composable
fun AnalyzeScreen(
    modifier: Modifier = Modifier,
    fridge: FridgeViewModel,
    onBackClick: () -> Unit,
    onManualClick: () -> Unit,
    onRetakeClick: () -> Unit,
    onSaveClick: () -> Unit,
    imageUri: String? = null,
    ingredientCatalog: IngredientCatalogViewModel = viewModel(),
    reviewModel: PhotoAnalysisViewModel? = null,
    entryToken: String? = null
) {
    val context = LocalContext.current.applicationContext
    val factory = remember(context) {
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T {
                val analyzer = IngredientAnalyzer(context)
                return PhotoAnalysisViewModel { analyzer.review(it.toUri()) } as T
            }
        }
    }
    val review = reviewModel ?: viewModel<PhotoAnalysisViewModel>(factory = factory)
    LaunchedEffect(review, imageUri, entryToken) { if(entryToken==null) review.start(imageUri) else review.startEntry(imageUri, entryToken) }
    LaunchedEffect(ingredientCatalog) { ingredientCatalog.load() }
    val save = rememberIngredientSave(fridge, onSaveClick)
    val sheet = LocalEntrySheet.current
    // Read snapshots in this composition, not inside SideEffect, so typing updates the guard.
    val hasDraft = review.editor.ingredients.any { it.name.isNotBlank() }
    val saveBusy = save.busy
    SideEffect { sheet?.busy = saveBusy; sheet?.draft = hasDraft }
    BackHandler(enabled = save.busy) { }
    val state = review.state
    val ready = (state as? PhotoAnalysisState.Ready)?.result
    val result = ready ?: (state as? PhotoAnalysisState.Empty)?.result
    fun leave(action: () -> Unit) {
        if (!save.busy) { review.cancel(); action() }
    }

    AddFlowScaffold(
        modifier = modifier,
        onBackClick = { if(sheet!=null) { if(!save.busy) onBackClick() } else leave(onBackClick) },
        title = "인식 결과 확인",
        bottomContent = {
            if (ready != null) {
                Row(Modifier.fillMaxWidth().toggleable(value = review.confirmed, role = Role.Checkbox,
                    enabled = !save.busy, onValueChange = review::confirm)
                    .padding(horizontal = 24.dp, vertical = 8.dp).testTag("confirm-photo-review"),
                    verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(checked = review.confirmed, onCheckedChange = null)
                    Spacer(Modifier.width(8.dp))
                    Text("사진과 재료 목록을 확인했어요", style = MaterialTheme.typography.bodyMedium)
                }
                fridge.ingredientSaveError?.let { Text(it, color = MaterialTheme.colorScheme.error) }
                Button(onClick = { save.submit(review.editor.ingredients.toList()) },
                    enabled = review.confirmed && !save.busy,
                    modifier = Modifier.fillMaxWidth(0.8f).heightIn(min = 52.dp).testTag("save-reviewed-ingredients")) {
                    Text(if (fridge.isSavingIngredients) "저장 중" else "저장")
                }
            } else if (state == PhotoAnalysisState.Loading) {
                OutlinedButton(onClick = review::cancel,
                    modifier = Modifier.fillMaxWidth(0.8f).heightIn(min = 52.dp)) { Text("인식 취소") }
            } else {
                Button(onClick = review::retry,
                    modifier = Modifier.fillMaxWidth(0.8f).heightIn(min = 52.dp)) { Text("다시 시도") }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                TextButton(onClick = { leave(onManualClick) }, enabled = !save.busy) { Text("직접 입력") }
                TextButton(onClick = { leave(onRetakeClick) }, enabled = !save.busy) { Text("다시 찍기") }
            }
        }
    ) {
        BoxWithConstraints(Modifier.fillMaxSize()) {
            val photoHeight = (maxHeight * .35f).coerceIn(72.dp, 160.dp)
            val recovery = state !is PhotoAnalysisState.Ready && state != PhotoAnalysisState.Loading
            val scroll = rememberScrollState()
            Column(Modifier.fillMaxSize().then(if (recovery) Modifier.verticalScroll(scroll) else Modifier)) {
                PhotoPreview(result?.imageUris?.takeIf { it.isNotEmpty() } ?: listOfNotNull(imageUri), photoHeight)
                if ((result?.imageUris?.size ?: 0) > 1) {
                    Text("여러 사진의 후보예요. 사진을 넘겨 비교해 주세요.", Modifier.padding(horizontal = 16.dp),
                        style = MaterialTheme.typography.bodySmall)
                }
                if (result?.mode == RecognitionMode.MOCK) {
                    Text("샘플 결과예요. 사진을 분석한 결과가 아니에요.",
                        Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.tertiaryContainer).padding(12.dp),
                        color = MaterialTheme.colorScheme.onTertiaryContainer, style = MaterialTheme.typography.bodySmall)
                }
                when (state) {
                    PhotoAnalysisState.Loading -> Column(Modifier.fillMaxWidth().weight(1f),
                        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                        CircularProgressIndicator(Modifier.testTag("recognition-progress"))
                        Text("사진에서 재료를 찾고 있어요", Modifier.padding(12.dp))
                    }
                    is PhotoAnalysisState.Ready -> EditableIngredientList(review.editor, ingredientCatalog.names,
                        Modifier.fillMaxWidth().weight(1f), enabled = !save.busy)
                    is PhotoAnalysisState.Empty -> RecoveryMessage("재료를 찾지 못했어요",
                        "재료가 잘 보이게 다시 찍거나 직접 입력해 주세요.")
                    is PhotoAnalysisState.Failed -> RecoveryMessage("인식을 완료하지 못했어요", state.message)
                    PhotoAnalysisState.Cancelled -> RecoveryMessage("인식을 취소했어요",
                        "다시 시도하거나 직접 입력할 수 있어요.")
                }
            }
        }
    }
}

@Composable
private fun RecoveryMessage(title: String, message: String) {
    Column(Modifier.fillMaxWidth().padding(20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Text(title, style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        Text(message, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun PhotoPreview(uris: List<String>, height: androidx.compose.ui.unit.Dp) {
    var selected by remember(uris) { mutableStateOf(0) }
    var enlarged by remember { mutableStateOf(false) }
    val uri = uris.getOrNull(selected)
    var failed by remember(uri) { mutableStateOf(uri == null) }
    if(enlarged && uri!=null) Dialog(onDismissRequest={enlarged=false}, properties=DialogProperties(usePlatformDefaultWidth=false)) {
        Surface { Column(Modifier.fillMaxSize()) {
            TextButton(onClick={enlarged=false}) { Text("사진 닫기") }
            AsyncImage(model=uri.toUri(),contentDescription="확대 원본 사진",modifier=Modifier.fillMaxWidth().weight(1f),contentScale=ContentScale.Fit)
        } }
    }

    Box(Modifier.fillMaxWidth().height(height).background(MaterialTheme.colorScheme.surfaceVariant)
        .testTag("review-photo").clickable(enabled=uri!=null) { enlarged=true }, contentAlignment = Alignment.Center) {
        if (uri != null) AsyncImage(model = uri.toUri(), contentDescription = "원본 사진",
            modifier = Modifier.fillMaxSize(), contentScale = ContentScale.Fit,
            onError = { failed = true })
        if (failed) Text("사진을 불러올 수 없어요", style = MaterialTheme.typography.bodySmall)
        if (uris.size > 1) {
            Row(Modifier.align(Alignment.BottomCenter).background(MaterialTheme.colorScheme.surface)) {
                TextButton(onClick = { selected = (selected - 1).coerceAtLeast(0) }, enabled = selected > 0) { Text("이전 사진") }
                Text("${selected + 1}/${uris.size}", Modifier.align(Alignment.CenterVertically))
                TextButton(onClick = { selected = (selected + 1).coerceAtMost(uris.lastIndex) }, enabled = selected < uris.lastIndex) { Text("다음 사진") }
            }
        }
    }
}
