// Usage events (fridge_add, recognition) added with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
// HE ingredient/exploration changes assisted by Codex, 2026-11-10; human review pending.
// Atomic multi-selection deletion assisted by Codex, 2026-11-03; human review pending.
// Fridge presentation/sorting and arrival-order updates assisted by Codex, 2026-11-02; human review pending.
// Restored and integrated with Codex, 2026-10-29; human review pending.
// AI-assisted with Codex (GPT-6.1 Sol), 2026-10-14; human review pending.
package com.example.mylittlechef.viewmodel

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mylittlechef.data.local.FridgeRepository
import com.example.mylittlechef.domain.FridgeInventory
import com.example.mylittlechef.domain.NoTelemetry
import com.example.mylittlechef.domain.Telemetry
import com.example.mylittlechef.domain.Usage
import com.example.mylittlechef.domain.UsageEvent
import com.example.mylittlechef.domain.InventoryRemoval
import com.example.mylittlechef.domain.RemovedInventoryItem
import com.example.mylittlechef.domain.restoreInventoryNames
import com.example.mylittlechef.model.Preset
import com.example.mylittlechef.model.Ingredient
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.launch

data class IngredientSaveCompletion(val id: Long, val ownerId: String)

class FridgeViewModel(
    private val repository: FridgeRepository? = null,
    private val telemetry: Telemetry = NoTelemetry
) : ViewModel() {
    private var ingredientSaveSequence = 0L
    private var ingredientEntryOwner: String? = null
    var ingredientSaveCompletion by mutableStateOf<IngredientSaveCompletion?>(null)
        private set
    var isSavingIngredients by mutableStateOf(false)
        private set
    var ingredientSaveError by mutableStateOf<String?>(null)
        private set

    fun prepareIngredientEntry(ownerId: String) {
        if (ingredientEntryOwner != ownerId) {
            ingredientEntryOwner = ownerId
            ingredientSaveError = null
            if (!isSavingIngredients) ingredientSaveCompletion = null
        }
    }

    fun consumeIngredientSave(completion: IngredientSaveCompletion): Boolean {
        if (ingredientSaveCompletion != completion) return false
        ingredientSaveCompletion = null
        return true
    }

    /** [source]: "manual" or "photo", for the usage data only. */
    fun saveIngredients(items: List<Ingredient>, ownerId: String, source: String = "manual") {
        if (isSavingIngredients || isSavingPantry || isRemovingIngredients || isRestoringIngredients || removingIngredient != null) return
        if (ingredientSaveCompletion?.ownerId == ownerId) return
        val names = FridgeInventory(items.map { it.name }).names
        if (names.isEmpty()) return
        ingredientSaveError = null
        val store = repository
        if (store == null) {
            addIngredients(items, source) // records the usage event itself
            ingredientSaveCompletion = IngredientSaveCompletion(++ingredientSaveSequence, ownerId)
            return
        }
        isSavingIngredients = true
        viewModelScope.launch {
            try {
                store.add(names)
                ingredientSaveCompletion = IngredientSaveCompletion(++ingredientSaveSequence, ownerId)
                telemetry.track(Usage(UsageEvent.FRIDGE_ADD, source = source, count = names.size))
            }
            catch (cancelled: CancellationException) { throw cancelled }
            catch (_: Exception) { ingredientSaveError = "재료를 저장하지 못했어요. 다시 시도해 주세요." }
            finally { isSavingIngredients = false }
        }
    }
    private var removalSequence = 0L
    var pendingRemoval by mutableStateOf<InventoryRemoval?>(null)
        private set
    var isRestoringIngredients by mutableStateOf(false)
        private set
    var undoError by mutableStateOf<String?>(null)
        private set

    fun dismissUndo(id: Long) {
        if (!isRestoringIngredients && pendingRemoval?.id == id) {
            pendingRemoval = null
            undoError = null
        }
    }

    fun undoRemoval(id: Long) {
        val receipt = pendingRemoval?.takeIf { it.id == id } ?: return
        if (isRestoringIngredients || isSavingPantry || isRemovingIngredients || removingIngredient != null) return
        undoError = null
        val source = repository
        if (source == null) {
            ingredients = restoreInventoryNames(ingredients.map { it.name }, receipt.items).map(::Ingredient)
            pendingRemoval = null
            return
        }
        isRestoringIngredients = true
        viewModelScope.launch {
            try {
                source.restoreRemoved(receipt.items)
                pendingRemoval = null
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                undoError = "복구하지 못했어요. 다시 시도해 주세요."
            } finally {
                isRestoringIngredients = false
            }
        }
    }

    var ingredients by mutableStateOf<List<Ingredient>>(emptyList())
        private set

    var isLoaded by mutableStateOf(repository == null)
        private set

    var removingIngredient by mutableStateOf<String?>(null)
        private set

    var isRemovingIngredients by mutableStateOf(false)
        private set

    var removalError by mutableStateOf<String?>(null)
        private set

    var isSavingPantry by mutableStateOf(false)
        private set
    var pantryError by mutableStateOf<String?>(null)
        private set

    init {
        repository?.let { source ->
            viewModelScope.launch {
                source.names.collect { names ->
                    ingredients = names.map(::Ingredient)
                    isLoaded = true
                }
            }
        }
    }

    /** [source] is where the items came from: photo, manual or suggestion (usage data only). */
    fun addIngredients(items: List<Ingredient>, source: String = "manual") {
        val names = items.map { it.name }
        if (names.isNotEmpty()) telemetry.track(Usage(UsageEvent.FRIDGE_ADD, source = source, count = names.size))
        ingredients = FridgeInventory(ingredients.map { it.name }).addAll(names).names.map(::Ingredient)
        repository?.let { source -> viewModelScope.launch { source.add(names) } }
    }

    // Explicit name correction only; DataStore selection update is one atomic transaction.
    fun renameIngredient(old: String, replacement: String) {
        val next = replacement.trim()
        if(next.isBlank() || old == next || ingredients.none { it.name == old } ||
            isSavingIngredients || isSavingPantry || isRemovingIngredients || isRestoringIngredients || removingIngredient != null) return
        ingredientSaveError = null
        val options = setOf(old, next)
        val source = repository
        if(source == null) {
            ingredients = FridgeInventory(ingredients.map { it.name }).replaceSelection(options,listOf(next)).names.map(::Ingredient)
            return
        }
        isSavingIngredients = true
        viewModelScope.launch {
            try { source.replaceSelection(options,listOf(next)) }
            catch(cancelled: CancellationException) { throw cancelled }
            catch(_: Exception) { ingredientSaveError = "이름을 바꾸지 못했어요. 다시 시도해 주세요." }
            finally { isSavingIngredients = false }
        }
    }

    fun removeIngredient(name: String) {
        val selectedName = name.trim()
        if (isSavingIngredients || isRestoringIngredients || isSavingPantry || isRemovingIngredients || removingIngredient != null ||
            ingredients.none { it.name.equals(selectedName, ignoreCase = true) }) return

        val removed = ingredients.mapIndexedNotNull { index, item ->
            if (item.name.equals(selectedName, ignoreCase = true)) RemovedInventoryItem(item.name, index) else null
        }
        removalError = null
        val source = repository
        if (source == null) {
            ingredients = FridgeInventory(ingredients.map { it.name }).remove(selectedName).names.map(::Ingredient)
            pendingRemoval = InventoryRemoval(++removalSequence, removed)
            undoError = null
            return
        }

        removingIngredient = selectedName
        viewModelScope.launch {
            try {
                // The repository flow updates the UI only after the write succeeds.
                source.remove(selectedName)
                pendingRemoval = InventoryRemoval(++removalSequence, removed)
                undoError = null
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                removalError = "재료를 삭제하지 못했어요. 다시 시도해 주세요."
            } finally {
                removingIngredient = null
            }
        }
    }

    fun dismissRemovalError() {
        removalError = null
    }

    fun removeIngredients(names: Set<String>, onRemoved: () -> Unit = {}) {
        if (isSavingIngredients || isRestoringIngredients || isSavingPantry || isRemovingIngredients || removingIngredient != null) return
        val selected = ingredients.map { it.name }.filter { it in names }.toSet()
        if (selected.isEmpty()) return
        val removed = ingredients.mapIndexedNotNull { index, item ->
            if (item.name in selected) RemovedInventoryItem(item.name, index) else null
        }
        removalError = null
        val source = repository
        if (source == null) {
            ingredients = FridgeInventory(ingredients.map { it.name }).removeAll(selected).names.map(::Ingredient)
            pendingRemoval = InventoryRemoval(++removalSequence, removed)
            undoError = null
            onRemoved()
            return
        }
        isRemovingIngredients = true
        viewModelScope.launch {
            try {
                // Publish inventory through the repository flow only after its one atomic write.
                source.removeAll(selected)
                pendingRemoval = InventoryRemoval(++removalSequence, removed)
                undoError = null
                onRemoved()
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                removalError = "재료를 삭제하지 못했어요. 다시 시도해 주세요."
            } finally {
                isRemovingIngredients = false
            }
        }
    }
    /** A photo's recognition finished: [found] items, or null when it failed. Usage data only. */
    fun onRecognition(found: Int?, durationMs: Long) {
        val status = when {
            found == null -> "error"
            found == 0 -> "empty"
            else -> "ok"
        }
        telemetry.track(Usage(UsageEvent.RECOGNITION, status = status, count = found, durationMs = durationMs))
    }

    fun updatePantryItems(selected: List<String>, onSaved: () -> Unit = {}) {
        if (isRestoringIngredients || isSavingPantry || isRemovingIngredients || removingIngredient != null) return
        val presets = (Preset.pantrySeasonings + Preset.pantryBasics).toSet()
        val desired = selected.filter { it in presets }.distinct()
        if (desired.isNotEmpty()) telemetry.track(Usage(UsageEvent.FRIDGE_ADD, source = "pantry", count = desired.size))
        pantryError = null
        val source = repository
        if (source == null) {
            ingredients = FridgeInventory(ingredients.map { it.name }).replaceSelection(presets, desired)
                .names.map(::Ingredient)
            onSaved()
            return
        }
        isSavingPantry = true
        viewModelScope.launch {
            try {
                source.replaceSelection(presets, desired)
                onSaved()
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (_: Exception) {
                pantryError = "기본 재료를 저장하지 못했어요. 다시 시도해 주세요."
            } finally {
                isSavingPantry = false
            }
        }
    }
}
