// Ingredient browsing and recommendation batches assisted by Codex, 2026-11-24; human review pending.
package com.example.mylittlechef.domain

private fun ingredientKey(name:String)=name.filterNot {it.isWhitespace()}.lowercase()
fun ingredientDishes(dishes:List<Dish>,name:String):List<Dish> {
    val key=ingredientKey(name)
    if(key.isEmpty()) return emptyList()
    return sortDishes(dishes.filter {dish -> (dish.have+dish.missing).any {ingredientKey(it)==key}},DishSort.FEWEST_MISSING)
}

/** Keep a real subset of the received candidates; never synthesize dishes or cooking availability. */
fun nextDishBatch(candidates:List<Dish>,previous:List<String>,seen:Set<String>,limit:Int=8):List<String> {
    val all=candidates.distinctBy {it.id}.map {it.id}
    val ranked=all.filter {it !in seen}+all.filter {it in seen && it !in previous}+all.filter {it in previous}
    return ranked.distinct().take(limit.coerceAtLeast(0))
}
