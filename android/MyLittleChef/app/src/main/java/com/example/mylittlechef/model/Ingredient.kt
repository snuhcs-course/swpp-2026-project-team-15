package com.example.mylittlechef.model

import androidx.annotation.DrawableRes

data class Ingredient(
    val name: String,

    // TODO: ingredient image resource
    @DrawableRes val imageRes: Int? = null
)
