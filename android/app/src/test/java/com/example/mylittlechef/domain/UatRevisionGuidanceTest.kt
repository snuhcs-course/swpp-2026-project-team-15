// Revision failure classification and cooking shade checks assisted by Codex, 2026-11-24.
package com.example.mylittlechef.domain
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.luminance
import com.example.mylittlechef.data.remote.ReviseResponse
import com.example.mylittlechef.data.remote.RevisionErrorDto
import com.example.mylittlechef.ui.recipe.cookingCardColor
import org.junit.Assert.*
import org.junit.Test

class UatRevisionGuidanceTest {
 @Test fun validationFailuresNeverBecomeIngredientRefusals() {
  listOf("unavailable_ingredient","mentions_unavailable","main_dropped","bad_reference","bad_kind","unexplained_change","incomplete","unknown").forEach {code ->
   val result=ReviseResponse("failed","test",null,null,null,RevisionErrorDto(code,"바꾼 레시피가 규칙을 어겨서 보여 드릴 수 없어요.")).toRevision()
   assertTrue(result is Revision.Failed)
   val message=(result as Revision.Failed).message
   assertFalse(message.contains("규칙"));assertFalse(message.contains("재료가 부족해"))
  }
 }
 @Test fun confirmedRefusalKeepsItsRealReasonAndUnknownFailuresHaveAFriendlyFallback() {
  assertEquals(Revision.Refused("김치가 없어서 조정할 수 없어요."),ReviseResponse("refused","test",null,null,"김치가 없어서 조정할 수 없어요.",null).toRevision())
  assertEquals(REVISION_FAILED_MESSAGE,revisionFailureMessage(null))
  assertTrue(revisionFailureMessage("unavailable_ingredient").contains("수정안에 포함"))
  assertTrue(revisionFailureMessage("main_dropped").contains("수정안에서"))
 }
 @Test fun shadesDarkenMonotonicallyAndSingleStepKeepsItsOriginalColor() {
  for(base in listOf(Color(0xFFE4ECDD),Color(0xFF444B42))) {
   val shades=(0..4).map {cookingCardColor(base,it,5)}
   assertEquals(base,shades.first())
   assertTrue(shades.zipWithNext().all {(a,b)->a.luminance()>b.luminance()})
   assertEquals(base,cookingCardColor(base,0,1))
   assertEquals(shades.last(),cookingCardColor(base,99,5))
   assertEquals(base,cookingCardColor(base,-1,5))
  }
 }
}
