// Camera target direction tests assisted by Codex, 2026-11-25.
package com.example.mylittlechef.domain
import org.junit.Assert.*
import org.junit.Test
class UatCaptureRotationTest {
 @Test fun allValidDirectionsMapToCameraXRotations() {
  for(degrees in 0..359) {
   val expected=when(degrees) {in 45..134->3;in 135..224->2;in 225..314->1;else->0}
   assertEquals("degrees=$degrees",expected,captureRotationForDegrees(degrees))
  }
 }
 @Test fun unknownDirectionDoesNotReplaceLastKnownRotation() {
  assertNull(captureRotationForDegrees(-1));assertNull(captureRotationForDegrees(360))
 }
 @Test fun shutterTracksTheSameDeviceEdgeAcrossCameraOrientations() {
  assertEquals(CaptureControlEdge.BOTTOM,captureControlEdge(false,0))
  assertEquals(CaptureControlEdge.RIGHT,captureControlEdge(true,1))
  assertEquals(CaptureControlEdge.LEFT,captureControlEdge(true,3))
 }
}
