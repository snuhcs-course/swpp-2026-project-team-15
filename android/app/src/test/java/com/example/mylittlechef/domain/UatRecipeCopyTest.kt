// UAT stage 3 tests assisted by Codex, 2026-11-24.
package com.example.mylittlechef.domain
import org.junit.Assert.*
import org.junit.Test
class UatRecipeCopyTest {
 @Test fun quantitiesAndUnitsAreKeptVerbatimAndUnknownAmountIsOmitted() {
  val text=copyRecipeIngredients("계란밥",false,listOf("소금" to "적당량","물" to "1/2 컵","계란" to null))
  assertEquals("계란밥 — 원본 레시피\n재료\n- 소금 적당량\n- 물 1/2 컵\n- 계란",text)
 }
 @Test fun revisedStepsUseVisibleOrderAndKeepMultilineText() {
  assertEquals("계란밥 — AI 수정본\n조리 방법\n1. 먼저 볶아요\n약불을 유지해요\n2. 마무리해요",copyRecipeSteps("계란밥",true,listOf("먼저 볶아요\n약불을 유지해요","마무리해요")))
 }
}
