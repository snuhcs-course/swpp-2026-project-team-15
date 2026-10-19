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
}
