package com.example.mylittlechef.model

/** Source text is preserved; the UI never invents a serving conversion. */
data class RecipeText(
    val name: String,
    val servings: String?,
    val ingredients: List<String>,
    val steps: List<String>,
    val cookingTime: String? = null
)

data class RecipeRevisionInfo(
    val status: String,
    val reason: String,
    val suggestion: RecipeText? = null,
    val changes: List<String> = emptyList()
)
