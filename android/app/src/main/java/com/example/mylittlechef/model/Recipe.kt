// Backend data wiring added with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.

// Modified with Codex (GPT-6 Luna), 2026-11-03; reviewed by Ahyoon Choi.
// Changes: nullable imageUrl

package com.example.mylittlechef.model

data class Recipe(
    val id: Long,
    val name: String,
    val time: Int,
    val serving: Int,
    val ingredients: List<Ingredient>,
    val steps: List<String>,

    val imageUrl: String? = null,

    // Missing items computed by the server (staples and synonyms considered); null for local data.
    val missing: List<Ingredient>? = null
)

data class AIRecipe(
    val original: Recipe,
    val serving: Int,
    val ingredients: List<Ingredient>,
    val steps: List<String>
)