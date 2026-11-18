// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.domain

import com.example.mylittlechef.data.remote.DishAdaptResponse
import com.example.mylittlechef.data.remote.DishDto
import com.example.mylittlechef.data.remote.DishVideoDto

data class DishVideo(
    val videoId: String,
    val title: String,
    val channel: String,
    val thumbnailUrl: String?
)

data class Dish(
    val id: String,
    val name: String,
    val category: String,
    val have: List<String>,
    val missing: List<String>,
    val reason: String,
    val searchUrl: String,
    val hasRecipe: Boolean = false
)

data class Substitution(val missing: String, val suggestion: String, val uses: List<String>)

data class DishAdaptation(
    val substitutions: List<Substitution>,
    val skipOk: List<String>,
    val note: String,
    val source: String
)

enum class DishSort(val label: String) {
    FEWEST_MISSING("부족한 재료 적은 순"),
    MOST_HAVE("가진 재료 많은 순"),
    NAME("이름순")
}

fun sortDishes(dishes: List<Dish>, sort: DishSort): List<Dish> = when (sort) {
    DishSort.FEWEST_MISSING -> dishes.sortedWith(compareBy<Dish> { it.missing.size }.thenByDescending { it.have.size })
    DishSort.MOST_HAVE -> dishes.sortedWith(compareByDescending<Dish> { it.have.size }.thenBy { it.missing.size })
    DishSort.NAME -> dishes.sortedBy { it.name }
}

/** Drops entries the server left incomplete instead of crashing on a null. */
fun DishDto.toDish(): Dish? {
    val id = id?.takeIf { it.isNotBlank() } ?: return null
    val name = name?.takeIf { it.isNotBlank() } ?: return null
    return Dish(
        id = id,
        name = name,
        category = category.orEmpty(),
        have = have.orEmpty(),
        missing = missing.orEmpty(),
        reason = reason.orEmpty(),
        searchUrl = DishLinks.safeSearchUrl(searchUrl, name),
        hasRecipe = hasRecipe == true
    )
}

fun DishVideoDto.toVideo(): DishVideo? {
    val id = videoId?.takeIf { DishLinks.isValidVideoId(it) } ?: return null
    return DishVideo(
        videoId = id,
        title = title.orEmpty(),
        channel = channel.orEmpty(),
        thumbnailUrl = thumbnailUrl?.takeIf { it.startsWith("https://") }
    )
}

fun DishAdaptResponse.toAdaptation() = DishAdaptation(
    substitutions = substitutions.orEmpty().mapNotNull {
        val missing = it.missing?.takeIf(String::isNotBlank) ?: return@mapNotNull null
        val suggestion = it.suggestion?.takeIf(String::isNotBlank) ?: return@mapNotNull null
        Substitution(missing, suggestion, it.uses.orEmpty())
    },
    skipOk = skipOk.orEmpty(),
    note = note.orEmpty(),
    source = source.orEmpty()
)
