// UAT stage 2 assisted by Codex, 2026-11-24; human review pending.
// UX2 layout/lifecycle changes assisted by Codex, 2026-11-19; human review pending.
// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui.onboarding

import com.example.mylittlechef.ui.components.DragSelectionGroup
import com.example.mylittlechef.ui.components.LocalSelectionTargets
import com.example.mylittlechef.ui.components.selectionTarget
import androidx.compose.ui.semantics.selected
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.platform.testTag
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.selection.toggleable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.semantics.testTag
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.model.Preset
import com.example.mylittlechef.ui.components.IngredientBadge
import kotlin.math.floor

@Composable
fun OnboardingPantry(
    selected: List<String>, onSelectedChange: (List<String>) -> Unit,
    onNext: () -> Unit, onBack: () -> Unit
) {
    OnboardingScaffold(
        backActive = true, jumpActive = true, onBackClick = onBack,
        onClick = onNext, onJumpClick = onNext,
        title = "집에 있는 기본 재료와 조미료", buttonText = "다음",
        buttonColor = MaterialTheme.colorScheme.primary,
        buttonTextColor = MaterialTheme.colorScheme.onPrimary
    ) { PantrySelectionContent(selected, onSelectedChange) }
}

@Composable
fun PantrySelectionContent(selected: List<String>, onSelectedChange: (List<String>) -> Unit, enabled: Boolean = true) {
    DragSelectionGroup(selected.toSet(), {onSelectedChange(it.toList())}, enabled=enabled) {
    Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text("있는 것만 골라주세요.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text("조미료", style = MaterialTheme.typography.labelMedium)
        OnboardingChoiceGrid(Preset.pantrySeasonings, selected, onSelectedChange, showBadges = true, enabled=enabled)
        Text("기본 재료", style = MaterialTheme.typography.labelMedium)
        OnboardingChoiceGrid(Preset.pantryBasics, selected, onSelectedChange, showBadges = true, enabled=enabled)
    }
    }
}

@Composable
internal fun OnboardingChoiceGrid(
    choices: List<String>, selected: List<String>, onSelectedChange: (List<String>) -> Unit,
    showBadges: Boolean = false, enabled: Boolean = true
) {
    if(LocalSelectionTargets.current == null) {
        DragSelectionGroup(selected.toSet(), {onSelectedChange(it.toList())}, enabled=enabled) {
            ChoiceGridContent(choices,selected,onSelectedChange,enabled)
        }
    } else ChoiceGridContent(choices,selected,onSelectedChange,enabled)
}

@Composable
private fun ChoiceGridContent(choices:List<String>,selected:List<String>,onSelectedChange:(List<String>)->Unit,enabled:Boolean) {
    val fontScale = LocalDensity.current.fontScale.coerceAtLeast(1f)
    BoxWithConstraints(Modifier.fillMaxWidth()) {
        val cellWidth = (if (choices == Preset.utensils) 92 else 72) * fontScale
        val columns = floor((maxWidth.value + 4) / (cellWidth + 4)).toInt()
            .coerceIn(1, if (choices == Preset.utensils) 3 else 4)
        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
            choices.chunked(columns).forEach { row ->
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    row.forEach { name ->
                        val checked = name in selected
                        val shape = RoundedCornerShape(14.dp)
                        Surface(
                            modifier = Modifier.weight(1f).heightIn(min = 60.dp)
                                .selectionTarget(name).testTag("choice-$name")
                                .semantics { this.selected = checked }
                                .toggleable(checked, enabled=enabled, role = Role.Checkbox, onValueChange = {
                                    onSelectedChange(if (checked) selected - name else selected + name)
                                }),
                            shape = shape,
                            color = MaterialTheme.colorScheme.background,
                            contentColor = if (checked) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant
                        ) {
                            Column(Modifier.padding(horizontal = 4.dp, vertical = 4.dp),
                                horizontalAlignment = Alignment.CenterHorizontally,
                                verticalArrangement = Arrangement.Center) {
                                ChoiceBadge(name, Modifier.clearAndSetSemantics { testTag="choice-icon-$name" }, selected=checked)
                                Row(verticalAlignment = Alignment.CenterVertically,
                                    horizontalArrangement = Arrangement.spacedBy(2.dp)) {
                                    Text(name, modifier = Modifier.weight(1f, fill = false), textAlign = TextAlign.Center,
                                        style = MaterialTheme.typography.bodySmall)
                                }
                            }
                        }
                    }
                    repeat(columns - row.size) { Spacer(Modifier.weight(1f)) }
                }
            }
        }
    }
}
