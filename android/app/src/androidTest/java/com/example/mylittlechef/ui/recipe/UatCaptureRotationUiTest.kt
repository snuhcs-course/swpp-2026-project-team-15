// Camera-only landscape and portrait result tests assisted by Codex, 2026-11-25.
package com.example.mylittlechef.ui.recipe
import android.app.Activity
import android.content.pm.ActivityInfo
import android.content.res.Configuration
import android.net.Uri
import android.view.View
import android.view.ViewGroup
import androidx.activity.compose.LocalActivity
import androidx.camera.view.PreviewView
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.ui.fridge.add.CaptureScreen
import com.example.mylittlechef.ui.theme.MyLittleChefTheme
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
class UatCaptureRotationUiTest {
 @get:Rule val rule=createComposeRule()
 private lateinit var activity:Activity
 private var show by mutableStateOf(true)
 private var uri:Uri?=null
 private var policyAtResult:Int?=null
 private var orientationAtResult:Int?=null
 private fun mount() {
  rule.setContent {MyLittleChefTheme {
   activity=LocalActivity.current!!
   if(show) CaptureScreen({show=false},{uri=it;policyAtResult=activity.requestedOrientation;orientationAtResult=activity.resources.configuration.orientation;show=false},{show=false})
   else Text("capture-result")
  }}
  ready()
 }
 private fun preview(view:View):PreviewView? {
  if(view is PreviewView) return view
  if(view is ViewGroup) for(i in 0 until view.childCount) preview(view.getChildAt(i))?.let {return it}
  return null
 }
 private fun ready() {rule.waitUntil(15000) {preview(activity.window.decorView)?.previewStreamState?.value==PreviewView.StreamState.STREAMING}}
 private fun rotate(request:Int,configuration:Int) {
  rule.runOnIdle {activity.requestedOrientation=request}
  rule.waitUntil(10000) {activity.resources.configuration.orientation==configuration}
  rule.waitForIdle()
 }
 private fun resultIsPortrait() {
  rule.waitUntil(15000) {uri!=null}
  rule.onNodeWithText("capture-result").assertIsDisplayed()
  assertEquals(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT,policyAtResult)
  assertEquals(Configuration.ORIENTATION_PORTRAIT,orientationAtResult)
  rule.waitUntil(10000) {activity.resources.configuration.orientation==Configuration.ORIENTATION_PORTRAIT}
  assertTrue(java.io.File(uri!!.path!!).length()>0)
 }
 @Test fun bothLandscapeDirectionsKeepShutterOnDeviceEdgeAndKeepModeUntilExit() {
  mount()
  try {
   rule.runOnIdle {assertEquals(ActivityInfo.SCREEN_ORIENTATION_SENSOR,activity.requestedOrientation)}
   rotate(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT,Configuration.ORIENTATION_PORTRAIT)
   rule.onNodeWithTag("capture-controls-BOTTOM").assertIsDisplayed()
   val portrait=rule.onNodeWithTag("capture-screen").fetchSemanticsNode().boundsInRoot
   assertTrue(rule.onNodeWithTag("capture-shutter").fetchSemanticsNode().boundsInRoot.center.y>portrait.top+portrait.height*.7f)
   rule.onNodeWithTag("capture-mode-video").performClick()
   for(direction in listOf(ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE,ActivityInfo.SCREEN_ORIENTATION_REVERSE_LANDSCAPE)) {
    rotate(direction,Configuration.ORIENTATION_LANDSCAPE)
    val edge=if(activity.window.decorView.display!!.rotation==3) "LEFT" else "RIGHT"
    rule.onNodeWithTag("capture-controls-$edge").assertIsDisplayed()
    rule.onNodeWithTag("capture-mode-video").assertIsSelected()
    val area=rule.onNodeWithTag("capture-screen").fetchSemanticsNode().boundsInRoot
    val shutter=rule.onNodeWithTag("capture-shutter").assertIsDisplayed().fetchSemanticsNode().boundsInRoot
    assertEquals(area.center.y,shutter.center.y,2f)
    if(edge=="RIGHT") assertTrue(shutter.center.x>area.left+area.width*.75f)
    else assertTrue(shutter.center.x<area.left+area.width*.25f)
    rule.onNodeWithTag("capture-gallery").assertIsDisplayed()
    rule.onNodeWithTag("capture-manual").assertIsDisplayed()
   }
   rule.onNodeWithTag("capture-manual").performClick()
   rule.onNodeWithText("capture-result").assertIsDisplayed()
   rule.runOnIdle {assertEquals(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT,activity.requestedOrientation)}
  } finally {rule.runOnIdle {show=false}}
 }
 private fun photo(orientation:Int,configuration:Int) {
  mount()
  try {
   rotate(orientation,configuration);ready()
   rule.onNodeWithTag("capture-shutter").performClick()
   resultIsPortrait()
   // Test callback only: never navigate to recognition or upload the test photo.
   java.io.File(uri!!.path!!).delete()
  } finally {rule.runOnIdle {show=false}}
 }
 @Test fun portraitPhotoReturnsToPortraitResults()=photo(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT,Configuration.ORIENTATION_PORTRAIT)
 @Test fun landscapePhotoReturnsImmediatelyToPortraitResults()=photo(ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE,Configuration.ORIENTATION_LANDSCAPE)
 @Test fun rotateDuringVideoSweepKeepsCaptureRunningAndReturnsPortrait() {
  mount()
  try {
   rule.onNodeWithTag("capture-mode-video").performClick();ready()
   rule.onNodeWithTag("capture-shutter").performClick()
   rule.onNodeWithText("냉장고를 천천히 훑어 주세요").assertIsDisplayed()
   rotate(ActivityInfo.SCREEN_ORIENTATION_LANDSCAPE,Configuration.ORIENTATION_LANDSCAPE)
   rule.onNodeWithText("냉장고를 천천히 훑어 주세요").assertIsDisplayed()
   resultIsPortrait()
  } finally {rule.runOnIdle {show=false}}
 }
}
