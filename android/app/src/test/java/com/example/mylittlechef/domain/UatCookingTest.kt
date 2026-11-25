// UAT stage 4 tests assisted by Codex, 2026-11-24.
package com.example.mylittlechef.domain
import org.junit.Assert.*
import org.junit.Test
class UatCookingTest {
 private val source=DishRecipe("demo","밥",videoTitle=null,videoChannel=null,servings=1,
  ingredients=listOf(RecipeIngredient("계란","1개",Availability.OWNED)),steps=listOf(RecipeStep(1,"원본 단계")),
  tips=emptyList(),uncertain=emptyList(),captionGaps=false)
 @Test fun snapshotUsesSelectedVersionAndEachRestartHasANewIdentity() {
  val revised=Revision.Revised(1,listOf(RevisedIngredient("두부",null)),listOf(RecipeStep(1,"두부를 볶아요")),emptyList(),emptyList())
  val original=startCookingRun(source)
  val run=startCookingRun(source,revised)
  assertFalse(original.revised);assertEquals("계란",original.recipe.ingredients.single().name)
  assertTrue(run.revised);assertEquals("두부",run.recipe.ingredients.single().name)
  assertEquals("두부를 볶아요",run.recipe.steps.single().text)
  assertEquals("계란",source.ingredients.single().name)
  assertNotEquals(run.id,startCookingRun(source,revised).id)
 }
 @Test fun calloutAlwaysUsesTheLargerNonOverlappingSafeArea() {
  val lower=guideCalloutZone(24f,700f,600f,660f,12f)
  assertTrue(lower.top+lower.height<=588f)
  val upper=guideCalloutZone(24f,700f,30f,80f,12f)
  assertTrue(upper.top>=92f);assertTrue(upper.top+upper.height<=700f)
 }
 @Test fun absentTargetStillLeavesTheGuideReadableWithinSafeBounds() {
  assertEquals(GuideZone(24f,376f),guideCalloutZone(24f,400f,null,null,12f))
 }
}
