// AI-assisted HE rules, 2026-11-10; human review pending.
package com.example.mylittlechef.domain

import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.model.Recipe
import java.text.Normalizer
import java.util.Locale

/** Mirrors reviewed server naming rules; never fuzzy-matches inventory or rewrites stored names. */
object IngredientNames {
    fun normalize(value: String) = Normalizer.normalize(value, Normalizer.Form.NFKC)
        .filterNot(Char::isWhitespace).lowercase(Locale.ROOT)
    private val synonyms = listOf(setOf("계란","달걀"),setOf("참치","참치캔","참치통조림"),
        setOf("김치","배추김치"),setOf("후추","후춧가루"))
    private val prepared = mapOf("마늘" to "다진마늘", "대파" to "다진파")
    fun expand(names: List<String>): Set<String> {
        val result = names.map(::normalize).filter(String::isNotBlank).toMutableSet()
        result.toList().forEach { prepared[it]?.let(result::add) }
        synonyms.forEach { if(it.any(result::contains)) result.addAll(it) }
        return result
    }
    fun resolve(names: List<String>, catalog: Map<String,Int>): Pair<List<Int>,List<String>> {
        val known = catalog.keys.map(::normalize).toSet()
        val unknown = names.filter { name -> expand(listOf(name)).none { it in known } }
        val available = expand(names.filterNot { it in unknown })
        return catalog.filterKeys { normalize(it) in available }.values.distinct().sorted() to unknown
    }
    fun usedOwnedNames(recipe: Recipe, inventory: List<Ingredient>): List<String> = inventory
        .filter { owned -> recipe.ingredients.any { normalize(it.name) in expand(listOf(owned.name)) } }
        .map { it.name }.distinct()
}
