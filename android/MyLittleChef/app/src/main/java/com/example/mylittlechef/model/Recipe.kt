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
    val missing: List<Ingredient>? = null
)

data class AIRecipe(
    val original: Recipe,
    val serving: Int,
    val ingredients: List<Ingredient>,
    val steps: List<String>
)