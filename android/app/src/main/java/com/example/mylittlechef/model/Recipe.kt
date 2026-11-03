// Recipe image compatibility adapted with Codex, 2026-11-03; human review pending.
// Backend data wiring added with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.model

import androidx.annotation.DrawableRes

data class Recipe(
    val id: Long,
    val name: String,
    val time: Int,
    val serving: Int,
    val ingredients: List<Ingredient>,
    val steps: List<String>,

    @DrawableRes val imageRes: Int? = null,

    // Missing items computed by the server (staples and synonyms considered); null for local data.
    val missing: List<Ingredient>? = null,
    val servingText: String? = null,
    val ingredientQuantities: List<String?> = emptyList(),
    val revisionCandidate: Boolean = false,
    val availabilityKnown: Boolean = true,
    val revisionAvailable: Boolean = false,
    // Optional server thumbnail; local drawable fallback and inventory UI stay compatible.
    val imageUrl: String? = null
)

data class AIRecipe(
    val original: Recipe,
    val serving: Int,
    val ingredients: List<Ingredient>,
    val steps: List<String>
)
