package com.example.mylittlechef.model

import androidx.annotation.DrawableRes

data class Recipe(
    val id: Long,
    val name: String,
    val time: Int,
    val serving: Int,
    val ingredients: List<Ingredient>,
    val steps: List<String>,

    @DrawableRes val imageRes: Int? = null
)

data class AIRecipe(
    val original: Recipe,
    val serving: Int,
    val ingredients: List<Ingredient>,
    val steps: List<String>
)