// Camera rotation assisted by Codex, 2026-11-25; human review pending.
package com.example.mylittlechef.domain

/** CameraX target rotation relative to the device's natural display orientation. */
fun captureRotationForDegrees(degrees:Int):Int? = when(degrees) {
    in 0..44, in 315..359 -> 0
    in 45..134 -> 3
    in 135..224 -> 2
    in 225..314 -> 1
    else -> null // Flat/unknown: retain the last valid direction.
}

/** Keep the shutter on the device's natural bottom edge as camera-only UI rotates. */
enum class CaptureControlEdge {BOTTOM,RIGHT,LEFT}
fun captureControlEdge(landscape:Boolean,displayRotation:Int):CaptureControlEdge = when {
    !landscape -> CaptureControlEdge.BOTTOM
    displayRotation==3 -> CaptureControlEdge.LEFT
    else -> CaptureControlEdge.RIGHT
}
