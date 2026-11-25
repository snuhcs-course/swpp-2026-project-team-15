// UAT stage 2 tests assisted by Codex, 2026-11-24.
package com.example.mylittlechef.domain
import org.junit.Assert.*
import org.junit.Test
class SelectionStrokeTest {
 @Test fun revisitingAnItemDoesNotToggleItAgain() {
  val stroke=SelectionStroke(true)
  assertTrue(stroke.visit("마늘"));assertTrue(stroke.visit("다진마늘"));assertFalse(stroke.visit("마늘"))
  assertTrue(stroke.selecting)
 }
 @Test fun deselectionDirectionIsFixedForTheWholeGesture() {
  val stroke=SelectionStroke(false)
  listOf("계란","두부","소금").forEach {assertTrue(stroke.visit(it));assertFalse(stroke.selecting)}
  assertFalse(stroke.visit("계란"))
  assertTrue(SelectionStroke(true).visit("계란"))
 }
}
