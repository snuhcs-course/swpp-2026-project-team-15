// Atomic multi-selection deletion assisted by Codex, 2026-11-03; human review pending.
// Fridge presentation/sorting and arrival-order updates assisted by Codex, 2026-11-02; human review pending.
// AI-assisted with Codex (GPT-6.1 Sol), 2026-10-14; human review pending.
package com.example.mylittlechef.domain

fun distinctNames(values: List<String>): List<String> =
    values.map(String::trim)
        .filter(String::isNotEmpty)
        .distinctBy(String::lowercase)

class FridgeInventory(names: List<String> = emptyList()) {
    val names: List<String> = distinctNames(names)

    fun addAll(values: List<String>): FridgeInventory = FridgeInventory(names + values)

    fun remove(value: String): FridgeInventory =
        FridgeInventory(names.filterNot { it.equals(value.trim(), ignoreCase = true) })

    // Bulk selection carries stored names, never appearance aliases or normalized guesses.
    fun removeAll(values: Set<String>): FridgeInventory =
        FridgeInventory(names.filterNot { it in values })

    // Retain arrival order for kept ingredients; append newly selected names only.
    fun replaceSelection(options: Set<String>, selected: List<String>): FridgeInventory {
        val desired = selected.filter { it in options }
        val retained = names.filter { it !in options || it in desired }
        return FridgeInventory(retained + desired)
    }
}
