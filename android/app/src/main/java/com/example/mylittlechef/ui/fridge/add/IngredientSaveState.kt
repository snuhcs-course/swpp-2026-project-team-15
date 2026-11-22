// Usage-data source added with Claude Code (Opus 5.5), 2026-11-20.
// AI-assisted lifecycle-safe HE save delivery, 2026-11-09; manual review pending.
package com.example.mylittlechef.ui.fridge.add

import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.repeatOnLifecycle
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.viewmodel.FridgeViewModel
import java.util.UUID

internal data class IngredientSaveAction(val busy: Boolean, val submit: (List<Ingredient>) -> Unit)

/** The retained ViewModel owns completion state, never a stale NavController callback. */
@Composable
internal fun rememberIngredientSave(
    fridge: FridgeViewModel,
    onSaved: () -> Unit,
    source: String = "manual" // usage data: how the items were entered
): IngredientSaveAction {
    val ownerId = rememberSaveable { UUID.randomUUID().toString() }
    val currentOnSaved by rememberUpdatedState(onSaved)
    val lifecycleOwner = LocalLifecycleOwner.current
    val completion = fridge.ingredientSaveCompletion?.takeIf { it.ownerId == ownerId }
    LaunchedEffect(ownerId) { fridge.prepareIngredientEntry(ownerId) }
    LaunchedEffect(completion, lifecycleOwner) {
        if (completion != null) lifecycleOwner.lifecycle.repeatOnLifecycle(Lifecycle.State.RESUMED) {
            if (fridge.consumeIngredientSave(completion)) currentOnSaved()
        }
    }
    return IngredientSaveAction(fridge.isSavingIngredients || completion != null) {
        fridge.saveIngredients(it, ownerId, source)
    }
}
