package com.example.mylittlechef.data.recipes

import com.google.gson.annotations.SerializedName
import java.util.Locale

data class CatalogIngredientDto(
    @SerializedName("ingredient_id") val id: Long,
    val name: String?
)

data class IngredientCatalogDto(val version: String?, val ingredients: List<CatalogIngredientDto>?)
data class ResolvedInventory(val ids: List<Long>, val unmapped: List<String>, val version: String)

fun IngredientCatalogDto.resolve(names: List<String>): ResolvedInventory {
    val token = requireNotNull(version) { "Missing ingredient catalog version" }
    require(token.matches(Regex("[a-f0-9]{64}"))) { "Invalid ingredient catalog version" }
    val rows = requireNotNull(ingredients) { "Missing ingredient catalog" }
    require(rows.all { it.id > 0 && !it.name.isNullOrBlank() }) { "Invalid catalog ingredient" }
    require(rows.map { it.id }.distinct().size == rows.size) { "Duplicate catalog IDs" }
    val byName = rows.groupBy { it.name!!.trim().lowercase(Locale.ROOT) }
    val ids = linkedSetOf<Long>()
    val unknown = linkedSetOf<String>()
    names.map(String::trim).filter(String::isNotBlank).forEach { name ->
        val key = name.lowercase(Locale.ROOT)
        val matches = byName[key] ?: if (key == "달걀") byName["계란"] else null
        if (matches?.size == 1) ids += matches.single().id else unknown += name
    }
    return ResolvedInventory(ids.toList(), unknown.toList(), token)
}
