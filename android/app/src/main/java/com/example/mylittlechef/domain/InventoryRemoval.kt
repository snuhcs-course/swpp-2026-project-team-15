// AI-assisted HE deletion recovery, 2026-11-09; manual review pending.
package com.example.mylittlechef.domain

data class RemovedInventoryItem(val name: String, val index: Int)
data class InventoryRemoval(val id: Long, val items: List<RemovedInventoryItem>)

/** Merge only deleted entries into the current inventory; never rewind unrelated writes. */
fun restoreInventoryNames(current: List<String>, removed: List<RemovedInventoryItem>): List<String> {
    val result = distinctNames(current).toMutableList()
    removed.sortedBy { it.index }.forEach { item ->
        if (result.none { it.equals(item.name, ignoreCase = true) }) {
            result.add(item.index.coerceIn(0, result.size), item.name)
        }
    }
    return distinctNames(result)
}
