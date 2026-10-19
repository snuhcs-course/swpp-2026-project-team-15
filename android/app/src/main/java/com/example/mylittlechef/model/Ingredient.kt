// AI-generated initial ingredient-model draft with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
package com.example.mylittlechef.model

import androidx.annotation.DrawableRes

data class Ingredient(
    val name: String,

    // TODO: ingredient image resource
    @DrawableRes val imageRes: Int? = null
)
