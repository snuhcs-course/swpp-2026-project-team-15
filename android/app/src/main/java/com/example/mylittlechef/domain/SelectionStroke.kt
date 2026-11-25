// UAT stage 2 assisted by Codex, 2026-11-24; human review pending.
package com.example.mylittlechef.domain

/** One gesture applies a fixed value once per identity, never a repeated toggle. */
class SelectionStroke(val selecting: Boolean) {
    private val visited = mutableSetOf<String>()
    fun visit(name: String): Boolean = visited.add(name)
}
