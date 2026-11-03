// AI-assisted with Codex, 2026-11-02; human review pending.
package com.example.mylittlechef.data.local

import android.content.Context
import com.example.mylittlechef.domain.IngredientPresentationCatalog

object IngredientPresentationProvider {
    @Volatile private var cached: IngredientPresentationCatalog? = null

    fun get(context: Context): IngredientPresentationCatalog = cached ?: synchronized(this) {
        cached ?: context.applicationContext.assets.open("ingredient_presentation.csv")
            .bufferedReader(Charsets.UTF_8).use { IngredientPresentationCatalog.fromCsv(it.readText()) }
            .also { cached = it }
    }
}
