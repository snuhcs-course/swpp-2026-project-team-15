package com.example.mylittlechef.data.recipes

import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import com.example.mylittlechef.model.RecipeRevisionInfo
import com.example.mylittlechef.model.RecipeText
import com.google.gson.annotations.SerializedName

data class IdRecommendRequest(
    @SerializedName("ingredient_ids") val ingredientIds: List<Long>,
    @SerializedName("revision_limit") val revisionLimit: Int = 3
)

data class SourceIngredientDto(
    @SerializedName("ingredient_id") val id: Long,
    val name: String?,
    @SerializedName("quantity_text") val quantity: String?
)
data class SourceStepDto(
    @SerializedName("step_number") val number: Int,
    val instruction: String?, val tip: String?
)
data class SourceRecipeDto(
    @SerializedName("recipe_id") val id: Long,
    val name: String?, val servings: String?,
    @SerializedName("cooking_time") val cookingTime: String?,
    val ingredients: List<SourceIngredientDto>?, val steps: List<SourceStepDto>?
) {
    fun text(): RecipeText {
        val title = requireNotNull(name).also { require(it.isNotBlank()) }
        val items = requireNotNull(ingredients)
        val instructions = requireNotNull(steps)
        require(items.isNotEmpty() && instructions.isNotEmpty())
        return RecipeText(title, servings, items.map {
            require(it.id > 0)
            listOfNotNull(requireNotNull(it.name), it.quantity?.takeIf(String::isNotBlank)).joinToString(" ")
        }, instructions.sortedBy { it.number }.map {
            require(it.number > 0)
            requireNotNull(it.instruction) + (it.tip?.let { tip -> "\n팁: $tip" } ?: "")
        }, cookingTime)
    }

    fun originalRecipe(): Recipe {
        require(id > 0)
        val original = text()
        return Recipe(id, original.name, leadingNumber(cookingTime), leadingNumber(servings),
            ingredients!!.map { Ingredient(requireNotNull(it.name)) }, original.steps, source = original)
    }
}

data class FilteringDto(
    @SerializedName("matched_count") val matched: Int?,
    @SerializedName("missing_count") val missing: Int?
)
data class RevisionErrorDto(val code: String?, val message: String?)
data class RevisionChangeDto(val kind: String?, val reason: String?)
data class ModelResultDto(
    @SerializedName("can_revise") val canRevise: Boolean?,
    val reason: String?, val changes: List<RevisionChangeDto>?,
    @SerializedName("revised_recipe") val revised: SourceRecipeDto?
)
data class RevisionDto(
    val status: String?, val result: ModelResultDto?, val error: RevisionErrorDto?,
    @SerializedName("not_attempted_reason") val notAttemptedReason: String?
) {
    fun info(): RecipeRevisionInfo {
        val outcome = requireNotNull(status)
        return when (outcome) {
            "revised" -> {
                val model = requireNotNull(result)
                require(model.canRevise == true && error == null && notAttemptedReason == null)
                RecipeRevisionInfo(outcome, model.reason.orEmpty(), requireNotNull(model.revised).text(),
                    requireNotNull(model.changes).map { "${requireNotNull(it.kind)}: ${requireNotNull(it.reason)}" })
            }
            "refused" -> {
                val model = requireNotNull(result)
                require(model.canRevise == false && model.revised == null && error == null && notAttemptedReason == null)
                require(!model.reason.isNullOrBlank())
                RecipeRevisionInfo(outcome, model.reason)
            }
            "failed" -> {
                require(result == null && notAttemptedReason == null)
                val failure = requireNotNull(error)
                RecipeRevisionInfo(outcome, listOfNotNull(failure.code, failure.message).joinToString(": "))
            }
            "not_attempted" -> {
                require(result == null && error == null)
                require(notAttemptedReason in setOf("outside_revision_limit", "shared_failure"))
                RecipeRevisionInfo(outcome, requireNotNull(notAttemptedReason))
            }
            else -> error("Unknown recipe revision status")
        }
    }
}
data class RecommendationEntryDto(
    @SerializedName("recipe_id") val id: Long,
    val original: SourceRecipeDto?, val filtering: FilteringDto?, val revision: RevisionDto?
) {
    fun recipe(available: Set<Long>): Recipe {
        val source = requireNotNull(original)
        require(id > 0 && source.id == id)
        val counts = requireNotNull(filtering)
        require(requireNotNull(counts.matched) >= 0 && requireNotNull(counts.missing) >= 0)
        return source.originalRecipe().copy(
            missing = source.ingredients!!.filter { it.id !in available }.distinctBy { it.id }
                .map { Ingredient(requireNotNull(it.name)) },
            filteringMissingCount = counts.missing,
            revision = requireNotNull(revision).info()
        )
    }
}
data class IdRecommendationsDto(
    val recipes: List<RecommendationEntryDto>?,
    @SerializedName("assumed_ingredient_ids") val assumedIds: List<Long>?
) {
    fun mapped(inventory: List<Long>): List<Recipe> {
        val assumed = requireNotNull(assumedIds)
        require(assumed == listOf(204L)) { "Unsupported assumed ingredient policy" }
        val available = inventory.toSet() + assumed.toSet()
        val entries = requireNotNull(recipes)
        require(entries.map { it.id }.distinct().size == entries.size)
        return entries.sortedWith(compareBy<RecommendationEntryDto> { requireNotNull(requireNotNull(it.filtering).missing) }
            .thenByDescending { requireNotNull(requireNotNull(it.filtering).matched) }.thenBy { it.id })
            .map { it.recipe(available) }
    }
}

private fun leadingNumber(text: String?): Int = Regex("^\\d+").find(text.orEmpty())?.value?.toIntOrNull() ?: 0
