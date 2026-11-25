// UAT stage 2 assisted by Codex, 2026-11-24; human review pending.
// Icon selection presentation assisted by Codex, 2026-11-19; human review pending.
package com.example.mylittlechef.ui.onboarding

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.R
import com.example.mylittlechef.ui.components.IngredientBadge
import com.example.mylittlechef.ui.components.SelectionBadge

@Composable
internal fun ChoiceBadge(name: String, modifier: Modifier = Modifier, selected: Boolean = false) {
    val resource = when(name) {
        "가스레인지" -> R.drawable.ic_choice_gas
        "인덕션" -> R.drawable.ic_choice_induction
        "오븐" -> R.drawable.ic_choice_oven
        "에어프라이어" -> R.drawable.ic_choice_airfryer
        "믹서기" -> R.drawable.ic_choice_blender
        "전자레인지" -> R.drawable.ic_choice_microwave
        "땅콩" -> R.drawable.ic_choice_peanut
        "견과류" -> R.drawable.ic_choice_nut
        "밀" -> R.drawable.ic_choice_wheat
        "우유" -> R.drawable.ic_ingredient_milk
        "달걀" -> R.drawable.ic_ingredient_egg
        "갑각류" -> R.drawable.ic_ingredient_shrimp
        "생선" -> R.drawable.ic_ingredient_fish
        "대두" -> R.drawable.ic_ingredient_beans
        else -> null
    }
    if(resource == null) IngredientBadge(name, modifier.testTag("choice-icon-$name"), 36.dp, selected)
    else SelectionBadge(name, resource, Color(0xFFE8EFE8), selected,
        modifier.testTag("choice-icon-$name"), 36.dp)
}
