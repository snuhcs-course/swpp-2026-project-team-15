// Ingredient browsing tests assisted by Codex, 2026-11-24.
package com.example.mylittlechef.domain
import org.junit.Assert.*
import org.junit.Test
class UatDishBrowsingTest {
 private fun dish(id:String,have:List<String>,missing:List<String>)=Dish(id,id,"",have,missing,"","")
 @Test fun ingredientMatchIsExactNormalizedAndOrderedByFeasibility() {
  val dishes=listOf(dish("needs",listOf("대파"),listOf("밥")),dish("ready",listOf("대 파"),emptyList()),dish("other",listOf("파프리카"),emptyList()))
  assertEquals(listOf("ready","needs"),ingredientDishes(dishes," 대파 ").map {it.id})
  assertTrue(ingredientDishes(dishes,"파").isEmpty())
  assertTrue(ingredientDishes(dishes,"").isEmpty())
 }
 @Test fun nextBatchUsesUnseenThenOtherCandidatesWithoutDuplicates() {
  val all=(1..20).map {dish("$it",emptyList(),emptyList())}
  val first=nextDishBatch(all,emptyList(),emptySet())
  val second=nextDishBatch(all,first,first.toSet())
  assertEquals(8,first.size);assertEquals((9..16).map {"$it"},second)
  val third=nextDishBatch(all,second,(first+second).toSet())
  assertEquals((17..20).map {"$it"},third.take(4));assertEquals(8,third.distinct().size)
  assertTrue(third.none {it in second})
 }
 @Test fun smallOrEmptyPoolDoesNotInventDishes() {
  val all=listOf(dish("one",emptyList(),emptyList()))
  assertEquals(listOf("one"),nextDishBatch(all+all,listOf("one"),setOf("one")))
  assertTrue(nextDishBatch(emptyList(),emptyList(),emptySet()).isEmpty())
 }
}
