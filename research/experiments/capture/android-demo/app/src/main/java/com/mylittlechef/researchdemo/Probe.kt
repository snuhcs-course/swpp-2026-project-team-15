// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
package com.mylittlechef.researchdemo

import android.content.Context
import android.graphics.ImageFormat
import android.graphics.SurfaceTexture
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureResult
import android.hardware.camera2.params.OutputConfiguration
import android.hardware.camera2.params.SessionConfiguration
import android.media.ImageReader
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.util.Size
import androidx.camera.camera2.interop.Camera2CameraInfo
import androidx.camera.camera2.interop.ExperimentalCamera2Interop
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.camera.core.Preview
import androidx.camera.core.SessionConfig
import androidx.camera.core.UseCase
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.video.Recorder
import androidx.camera.video.VideoCapture
import androidx.camera.view.PreviewView
import androidx.lifecycle.LifecycleOwner
import org.json.JSONArray
import org.json.JSONObject
import java.io.File
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicInteger

/** Tries use-case combinations on the rear camera and dumps camera characteristics to probe.json. */
@OptIn(ExperimentalCamera2Interop::class)
class Probe(
    private val ctx: Context,
    private val owner: LifecycleOwner,
    private val provider: ProcessCameraProvider,
    private val previewView: PreviewView,
    private val buildAnalysis: (String) -> ImageAnalysis,
) {
    private val handler = Handler(Looper.getMainLooper())
    private val results = JSONArray()
    private val sel = CameraSelector.DEFAULT_BACK_CAMERA

    private class Combo(val name: String, val res: String, val preview: Boolean, val capture: Boolean, val video: Boolean)

    private val combos = listOf(
        Combo("Preview+ImageAnalysis", "1280x720", true, false, false),
        Combo("Preview+ImageAnalysis+ImageCapture", "1280x720", true, true, false),
        Combo("Preview+ImageAnalysis+VideoCapture", "1280x720", true, false, true),
        Combo("Preview+ImageAnalysis+ImageCapture+VideoCapture", "1280x720", true, true, true),
        Combo("Preview+ImageAnalysis(1280x960, not in the YUV size list)", "1280x960", true, false, false),
        Combo("Preview+ImageAnalysis(960x720)", "960x720", true, false, false),
        Combo("Preview+ImageAnalysis(1440x1080)", "1440x1080", true, false, false),
        Combo("Preview+ImageAnalysis(1920x1080)+ImageCapture+VideoCapture", "1920x1080", true, true, true),
        Combo("ImageAnalysis only", "1280x720", false, false, false),
    )

    fun run(done: (File) -> Unit) {
        provider.unbindAll()
        step(0, done)
    }

    private fun step(i: Int, done: (File) -> Unit) {
        if (i >= combos.size) {
            provider.unbindAll()
            val out = File(ctx.getExternalFilesDir(null), "probe.json")
            val root = JSONObject()
                .put("device", "${Build.MODEL} API ${Build.VERSION.SDK_INT}")
                .put("combinations", results)
                .put("camera", runCatching { characteristics() }.getOrElse { JSONObject().put("error", it.toString()) })
            out.writeText(root.toString(2))
            Log.i(RunRecorder.TAG, "PROBE_DONE ${out.absolutePath}")
            done(out)
            return
        }
        val c = combos[i]
        val frames = AtomicInteger()
        val r = JSONObject().put("name", c.name)
        val cases = ArrayList<UseCase>()
        val analysis = buildAnalysis(c.res)
        analysis.setAnalyzer(Executors.newSingleThreadExecutor()) { img -> frames.incrementAndGet(); img.close() }
        if (c.preview) cases += Preview.Builder().build().also { it.surfaceProvider = previewView.surfaceProvider }
        cases += analysis
        if (c.capture) cases += ImageCapture.Builder().build()
        if (c.video) cases += VideoCapture.withOutput(Recorder.Builder().build())
        r.put("use_cases", JSONArray(cases.map { it.javaClass.simpleName }))
        try {
            val supported = runCatching { provider.getCameraInfo(sel).isSessionConfigSupported(SessionConfig(useCases = cases)) }
            r.put("CameraInfo.isSessionConfigSupported", supported.getOrNull() ?: "n/a: ${supported.exceptionOrNull()}")
            provider.unbindAll()
            val cam = provider.bindToLifecycle(owner, sel, *cases.toTypedArray())
            r.put("bind", "ok")
            handler.postDelayed({
                r.put("camera_state", cam.cameraInfo.cameraState.value?.let { "${it.type} error=${it.error?.code}" } ?: "null")
                r.put("analysis_frames_in_2s", frames.get())
                r.put("analysis_resolution", analysis.resolutionInfo?.resolution?.toString() ?: "n/a")
                results.put(r)
                Log.i(RunRecorder.TAG, "PROBE ${r}")
                step(i + 1, done)
            }, 2000)
        } catch (e: Exception) {
            r.put("bind", "exception").put("exception", "${e.javaClass.name}: ${e.message}")
            results.put(r)
            Log.i(RunRecorder.TAG, "PROBE $r")
            step(i + 1, done)
        }
    }

    private fun characteristics(): JSONObject {
        val cameraId = Camera2CameraInfo.from(provider.getCameraInfo(sel)).cameraId
        val mgr = ctx.getSystemService(Context.CAMERA_SERVICE) as CameraManager
        val ch = mgr.getCameraCharacteristics(cameraId)
        val map = ch.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)!!
        fun sizes(a: Array<Size>?) = JSONArray((a ?: emptyArray()).map { "${it.width}x${it.height}" })
        val wanted = listOf(
            CaptureResult.SENSOR_EXPOSURE_TIME, CaptureResult.SENSOR_SENSITIVITY, CaptureResult.SENSOR_FRAME_DURATION,
            CaptureResult.LENS_FOCUS_DISTANCE, CaptureResult.LENS_STATE, CaptureResult.CONTROL_AF_STATE,
            CaptureResult.CONTROL_AE_STATE, CaptureResult.SENSOR_TIMESTAMP,
        )
        val available = ch.availableCaptureResultKeys.map { it.name }.toSet()
        val keys = JSONObject()
        wanted.forEach { keys.put(it.name, it.name in available) }
        val sessionTests = runCatching { sessionConfigTests(mgr, cameraId, map.getOutputSizes(ImageFormat.YUV_420_888)) }
            .getOrElse { JSONArray().put("error: $it") }
        return JSONObject()
            .put("camera_id", cameraId)
            .put("hardware_level", ch.get(CameraCharacteristics.INFO_SUPPORTED_HARDWARE_LEVEL))
            .put("hardware_level_legend", "0=LIMITED 1=FULL 2=LEGACY 3=LEVEL_3 4=EXTERNAL")
            .put("timestamp_source", ch.get(CameraCharacteristics.SENSOR_INFO_TIMESTAMP_SOURCE))
            .put("timestamp_source_legend", "0=UNKNOWN 1=REALTIME")
            .put("min_focus_distance_diopter", ch.get(CameraCharacteristics.LENS_INFO_MINIMUM_FOCUS_DISTANCE)?.toDouble())
            .put("ae_target_fps_ranges", JSONArray(ch.get(CameraCharacteristics.CONTROL_AE_AVAILABLE_TARGET_FPS_RANGES)!!.map { it.toString() }))
            .put("output_sizes_yuv_420_888", sizes(map.getOutputSizes(ImageFormat.YUV_420_888)))
            .put("output_sizes_preview_surface_texture", sizes(map.getOutputSizes(SurfaceTexture::class.java)))
            .put("output_sizes_jpeg", sizes(map.getOutputSizes(ImageFormat.JPEG)))
            .put("available_capture_result_keys_total", available.size)
            .put("wanted_result_keys_available", keys)
            .put("session_configuration_supported", sessionTests)
    }

    /** CameraManager.getCameraDeviceSetup (API 35) tests stream combinations without opening the camera. */
    private fun sessionConfigTests(mgr: CameraManager, id: String, yuvSizes: Array<Size>): JSONArray {
        val out = JSONArray()
        if (Build.VERSION.SDK_INT < 35 || !mgr.isCameraDeviceSetupSupported(id)) return out.put("CameraDeviceSetup not available")
        val setup = mgr.getCameraDeviceSetup(id)!!
        val cases = listOf(
            "YUV 1280x960 + YUV 1920x1080" to listOf(Size(1280, 960), Size(1920, 1080)),
            "YUV 1280x960 + YUV 1920x1080 + JPEG max" to listOf(Size(1280, 960), Size(1920, 1080), null),
        )
        for ((name, spec) in cases) {
            val readers = ArrayList<ImageReader>()
            val configs = spec.mapIndexed { n, s ->
                val reader = if (s == null) ImageReader.newInstance(4000, 3000, ImageFormat.JPEG, 1)
                else ImageReader.newInstance(s.width, s.height, ImageFormat.YUV_420_888, 1)
                readers += reader
                OutputConfiguration(reader.surface)
            }
            val sc = SessionConfiguration(SessionConfiguration.SESSION_REGULAR, configs, Executors.newSingleThreadExecutor(),
                object : android.hardware.camera2.CameraCaptureSession.StateCallback() {
                    override fun onConfigured(session: android.hardware.camera2.CameraCaptureSession) {}
                    override fun onConfigureFailed(session: android.hardware.camera2.CameraCaptureSession) {}
                })
            val r = runCatching { setup.isSessionConfigurationSupported(sc) }
            out.put(JSONObject().put("streams", name).put("supported", r.getOrNull() ?: "exception: ${r.exceptionOrNull()}"))
            readers.forEach { it.close() }
        }
        return out
    }
}
