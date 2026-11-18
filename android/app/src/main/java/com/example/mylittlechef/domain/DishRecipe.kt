// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-18; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.domain

import com.example.mylittlechef.data.remote.RecipeViewResponse
import com.example.mylittlechef.data.remote.ReviseResponse

enum class Availability { OWNED, ASSUMED, UNAVAILABLE }

data class RecipeIngredient(val name: String, val amount: String?, val availability: Availability)

data class RecipeStep(val n: Int, val text: String)

/** The recipe of one dish as the server stored it, with what the fridge holds of each ingredient. */
data class DishRecipe(
    val dishId: String,
    val name: String,
    val videoTitle: String?,
    val videoChannel: String?,
    val servings: Int?,
    val ingredients: List<RecipeIngredient>,
    val steps: List<RecipeStep>,
    val tips: List<String>,
    val uncertain: List<String>,
    val captionGaps: Boolean,
    /** True when the recipe was written from the video itself rather than from its captions. */
    val fromVideo: Boolean = false
) {
    val hasMissing get() = ingredients.any { it.availability == Availability.UNAVAILABLE }
}

data class RevisedIngredient(val name: String, val amount: String?)

/** One change of the revised recipe: the reason and the original rows and steps (1-based) it touches. */
data class RecipeChange(val reason: String, val ingredientRefs: List<Int>, val stepRefs: List<Int>)

sealed interface Revision {
    data class Revised(
        val servings: Int?,
        val ingredients: List<RevisedIngredient>,
        val steps: List<RecipeStep>,
        val tips: List<String>,
        val changes: List<RecipeChange>
    ) : Revision

    data class Refused(val reason: String) : Revision
    data class Failed(val message: String) : Revision
}

private fun availabilityOf(value: String?) = when (value) {
    "owned" -> Availability.OWNED
    "assumed" -> Availability.ASSUMED
    else -> Availability.UNAVAILABLE
}

/** Null when the answer lacks what the screen needs (a recipe without ingredients or steps). */
fun RecipeViewResponse.toDishRecipe(): DishRecipe? {
    val source = recipe ?: return null
    val id = dishId?.takeIf { it.isNotBlank() } ?: return null
    val rows = source.ingredients.orEmpty()
    val levels = availability.orEmpty()
    val ingredients = rows.mapIndexedNotNull { i, row ->
        val rowName = row.name?.takeIf { it.isNotBlank() } ?: return@mapIndexedNotNull null
        RecipeIngredient(rowName, row.amount?.takeIf { it.isNotBlank() }, availabilityOf(levels.getOrNull(i)))
    }
    val steps = source.steps.orEmpty().mapIndexedNotNull { i, step ->
        step.text?.takeIf { it.isNotBlank() }?.let { RecipeStep(step.n ?: (i + 1), it) }
    }
    if (ingredients.isEmpty() || steps.isEmpty()) return null
    return DishRecipe(
        dishId = id,
        name = name.orEmpty(),
        videoTitle = source.video?.title?.takeIf { it.isNotBlank() },
        videoChannel = source.video?.channel?.takeIf { it.isNotBlank() },
        servings = source.servings,
        ingredients = ingredients,
        steps = steps,
        tips = source.tips.orEmpty().filter { it.isNotBlank() },
        uncertain = source.uncertain.orEmpty().filter { it.isNotBlank() },
        captionGaps = source.captionGaps == true,
        fromVideo = source.source == "ai_structured_from_video"
    )
}

const val REVISION_FAILED_MESSAGE = "바꾼 레시피를 보여 드릴 수 없어요. 다시 시도해 주세요."

/** Null when the status is unknown, so the screen shows its error state instead of guessing. */
fun ReviseResponse.toRevision(): Revision? = when (status) {
    "revised" -> {
        val recipe = revised
        val ingredients = recipe?.ingredients.orEmpty().mapNotNull { row ->
            row.name?.takeIf { it.isNotBlank() }?.let { RevisedIngredient(it, row.amount?.takeIf { a -> a.isNotBlank() }) }
        }
        val steps = recipe?.steps.orEmpty().mapIndexedNotNull { i, step ->
            step.text?.takeIf { it.isNotBlank() }?.let { RecipeStep(step.n ?: (i + 1), it) }
        }
        if (recipe == null || ingredients.isEmpty() || steps.isEmpty()) null
        else Revision.Revised(
            servings = recipe.servings,
            ingredients = ingredients,
            steps = steps,
            tips = recipe.tips.orEmpty().filter { it.isNotBlank() },
            changes = changes.orEmpty().mapNotNull { c ->
                c.reason?.takeIf { it.isNotBlank() }
                    ?.let { RecipeChange(it, c.ingredientRefs.orEmpty(), c.stepRefs.orEmpty()) }
            }
        )
    }
    "refused" -> Revision.Refused(refusalReason?.takeIf { it.isNotBlank() } ?: "이 재료로는 바꾸기 어려워요.")
    "failed" -> Revision.Failed(error?.message?.takeIf { it.isNotBlank() } ?: REVISION_FAILED_MESSAGE)
    else -> null
}
