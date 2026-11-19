// AI-assisted selected-recipe UI, 2026-11-10; human review pending.
package com.example.mylittlechef.ui.recipe

import androidx.compose.foundation.background
import androidx.compose.animation.animateContentSize
import androidx.compose.animation.core.tween
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.domain.IngredientNames
import com.example.mylittlechef.model.Recipe
import com.example.mylittlechef.viewmodel.*

@Composable
fun SelectedRevisionPanel(state: SelectedRevisionState, showingSuggestion: Boolean,
    onRequest: () -> Unit, onToggle: () -> Unit, onCancel: () -> Unit,
    onOriginal: () -> Unit, onReview: () -> Unit, onIgnore: () -> Unit, onReload: () -> Unit) {
    var confirmOmission by remember { mutableStateOf(false) }
    var changesExpanded by rememberSaveable(state.original?.id) { mutableStateOf(false) }
    Column(Modifier.animateContentSize(tween(160)), verticalArrangement = Arrangement.spacedBy(10.dp)) {
        Text(if(showingSuggestion && state.status == RevisionStatus.REVISED) "AI 수정 제안" else "원본 레시피",
            style=MaterialTheme.typography.titleMedium)
        Text("보유 재료를 고려해 이 요리의 재료와 조리법을 조정해요.",style=MaterialTheme.typography.bodyMedium)
        if(state.mode == "mock") Text("테스트용 샘플 응답이에요. 실제 AI 판단이 아니에요.",
            Modifier.fillMaxWidth().background(MaterialTheme.colorScheme.tertiaryContainer).padding(10.dp),
            color=MaterialTheme.colorScheme.onTertiaryContainer,style=MaterialTheme.typography.bodySmall)
        when(state.status) {
            RevisionStatus.LOADING -> {
                Row(verticalAlignment=Alignment.CenterVertically,horizontalArrangement=Arrangement.spacedBy(12.dp)) {
                    CircularProgressIndicator(Modifier.size(28.dp).testTag("selected-revision-progress"),
                        color=MaterialTheme.colorScheme.primary)
                    Text("이 요리의 제안을 만들고 있어요")
                }
                OutlinedButton(onClick=onCancel,modifier=Modifier.heightIn(min=48.dp)) { Text("요청 취소") }
            }
            RevisionStatus.REVISED -> {
                OutlinedButton(onClick=onToggle,modifier=Modifier.heightIn(min=48.dp)) {
                    Text(if(showingSuggestion) "원본 보기" else "AI 제안 보기")
                }
                if(showingSuggestion) {
                    state.suggestion?.let { Text(it.name,style=MaterialTheme.typography.titleMedium) }
                    state.message?.takeIf(String::isNotBlank)?.let { Text(it) }
                    TextButton(onClick={changesExpanded=!changesExpanded}) { Text(if(changesExpanded) "변경 내용 접기" else "변경 내용 보기") }
                    if(changesExpanded) {
                        val original=state.original; val revised=state.suggestion
                        if(original != null && revised != null) {
                            val deltas=ingredientChanges(original,revised)
                            if(deltas.isNotEmpty()) Text("재료 변경",style=MaterialTheme.typography.labelLarge)
                            deltas.forEach { Text("• $it") }
                            if(original.steps != revised.steps) {
                                Text("조리 단계 변경",style=MaterialTheme.typography.labelLarge)
                                (0 until maxOf(original.steps.size,revised.steps.size)).forEach { index ->
                                    val before=original.steps.getOrNull(index); val after=revised.steps.getOrNull(index)
                                    if(before != after) Text("${index+1}단계: ${before ?: "없음"} → ${after ?: "제외"}")
                                }
                            }
                        }
                        state.changes.forEach { Text("• ${it.reason}") }
                    }
                    Text("조리 시간은 원본 기준이에요.",style=MaterialTheme.typography.bodySmall)
                }
            }
            RevisionStatus.IDLE -> Button(onClick=onRequest,modifier=Modifier.fillMaxWidth().heightIn(min=48.dp),shape=RoundedCornerShape(13.dp)) { Text("내 재료로 바꾸기") }
            else -> {
                val message=if(state.mode == "mock" && state.message.orEmpty().startsWith("MOCK ONLY"))
                    "샘플 응답이므로 수정 제안을 만들지 않았어요." else state.message.orEmpty()
                Text(message.ifBlank { "조정하기 어려워요. 원본 레시피를 확인해 주세요." },
                    color=if(state.problem == SelectedProblem.CANCELLED || state.status == RevisionStatus.REFUSED)
                        MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.error)
                FlowRow(horizontalArrangement=Arrangement.spacedBy(8.dp)) {
                    if(state.problem == SelectedProblem.NOT_FOUND) TextButton(onClick=onReload) { Text("목록 다시 불러오기") }
                    else TextButton(onClick=onRequest) { Text(if(state.problem == SelectedProblem.UNSUPPORTED) "지원 다시 확인" else "다시 시도") }
                    TextButton(onClick=onOriginal) { Text("원본 보기") }
                    TextButton(onClick=onReview) { Text("재료 확인") }
                }
                if(state.problem == SelectedProblem.UNREGISTERED) {
                    Text("이름 확인: ${state.unknownNames.joinToString(", ")}")
                    OutlinedButton(onClick={confirmOmission=true}) { Text("미등록 재료 제외하기") }
                }
            }
        }
        if(state.status == RevisionStatus.LOADING || state.problem in setOf(SelectedProblem.CANCELLED,SelectedProblem.TIMEOUT))
            Text("대기를 취소해도 이미 시작된 서버 처리는 계속될 수 있어요.",style=MaterialTheme.typography.bodySmall)
        Text("알레르기·조리도구 조건은 반영되지 않아요. 직접 확인해 주세요.",style=MaterialTheme.typography.bodySmall)
    }
    if(confirmOmission && state.problem == SelectedProblem.UNREGISTERED) AlertDialog(
        onDismissRequest={confirmOmission=false},title={Text("이 재료를 제외할까요?")},
        text={Column(Modifier.verticalScroll(rememberScrollState())) {
            Text(state.unknownNames.joinToString(", "))
            Text("이번 AI 요청에서만 제외하며, 냉장고에서는 삭제하지 않아요.")
        }},
        confirmButton={TextButton(onClick={confirmOmission=false;onIgnore()}) {Text("이 재료 없이 요청")}},
        dismissButton={TextButton(onClick={confirmOmission=false}) {Text("취소")}})
}

private fun ingredientChanges(before: Recipe, after: Recipe): List<String> {
    fun rows(recipe: Recipe) = recipe.ingredients.indices.groupBy { IngredientNames.normalize(recipe.ingredients[it].name) }
        .mapValues { (_,indices) -> indices.joinToString(" / ") { index ->
            recipe.ingredients[index].name + recipe.ingredientQuantities.getOrNull(index)?.let { " $it" }.orEmpty()
        } }
    val originals=rows(before); val revised=rows(after)
    return (originals.keys+revised.keys).distinct().mapNotNull { key ->
        if(originals[key] == revised[key]) null else "${originals[key] ?: "없음"} → ${revised[key] ?: "제외"}"
    }
}
