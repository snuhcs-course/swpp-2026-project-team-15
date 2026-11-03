// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
package com.mylittlechef.researchdemo

import android.graphics.Color
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.util.Log
import android.util.Size
import android.view.Gravity
import android.view.ViewGroup
import android.view.WindowManager
import android.widget.Button
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.TextView
import androidx.activity.ComponentActivity
import androidx.camera.camera2.interop.Camera2Interop
import androidx.camera.camera2.interop.ExperimentalCamera2Interop
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import org.opencv.android.OpenCVLoader
import java.io.File
import java.util.concurrent.Executors

@OptIn(ExperimentalCamera2Interop::class)
class MainActivity : ComponentActivity() {
    private val resolutions = listOf("640x480", "960x720", "1440x1080", "1280x720", "1920x1080", "1280x960")
    private var res = "1280x720"
    private val analysisExecutor = Executors.newSingleThreadExecutor()
    private val main = Handler(Looper.getMainLooper())
    private lateinit var recorder: RunRecorder
    private lateinit var provider: ProcessCameraProvider
    private lateinit var previewView: PreviewView
    private lateinit var status: TextView
    private lateinit var resButton: Button
    private lateinit var recordButton: Button
    private var busy = false
    private var arm = Arm.OVERLAP
    private var cap = ArmSelector.MIN_CAP
    private lateinit var armButton: Button
    private var liveMode = RunRecorder.LiveMode.OFF
    private var autoStopGroups = 0

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        check(OpenCVLoader.initLocal()) { "OpenCV native library failed to load" }
        recorder = RunRecorder(this, analysisExecutor)
        buildUi()
        intent.getStringExtra("res")?.let { if (it in resolutions) res = it }
        Arm.parse(intent.getStringExtra("arm"))?.let { arm = it }
        cap = ArmSelector.clampCap(intent.getIntExtra("cap", cap))
        liveMode = RunRecorder.LiveMode.parse(intent.getStringExtra("live"))
        autoStopGroups = intent.getIntExtra("autostop", 0)
        updateArmButton()
        resButton.text = "Analysis: $res (tap to change)"
        ProcessCameraProvider.getInstance(this).addListener({
            provider = ProcessCameraProvider.getInstance(this).get()
            bindCamera()
            handleIntent()
        }, ContextCompat.getMainExecutor(this))
    }

    private fun buildUi() {
        previewView = PreviewView(this)
        status = TextView(this).apply { setTextColor(Color.YELLOW); setBackgroundColor(0x99000000.toInt()); setPadding(16, 16, 16, 16); textSize = 14f }
        resButton = Button(this).apply {
            setOnClickListener {
                if (busy) return@setOnClickListener
                res = resolutions[(resolutions.indexOf(res) + 1) % resolutions.size]
                text = "Analysis: $res (tap to change)"
                bindCamera()
            }
        }
        armButton = Button(this).apply {
            setOnClickListener {
                if (busy) return@setOnClickListener
                arm = Arm.entries[(arm.ordinal + 1) % Arm.entries.size]
                updateArmButton()
            }
        }
        recordButton = Button(this).apply {
            text = "RECORD 5 s"; textSize = 28f
            setOnClickListener { startRun(5, 0) }
        }
        val probeButton = Button(this).apply { text = "Probe"; setOnClickListener { startProbe() } }
        val bottom = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            addView(status); addView(resButton); addView(armButton)
            addView(recordButton, LinearLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, 300))
            addView(probeButton)
        }
        setContentView(FrameLayout(this).apply {
            addView(previewView)
            addView(bottom, FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT, Gravity.BOTTOM))
        })
    }

    fun buildAnalysis(label: String, fps: Int? = null): ImageAnalysis {
        val (w, h) = label.split("x").map { it.toInt() }
        val builder = ImageAnalysis.Builder()
            .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST)
            .setOutputImageFormat(ImageAnalysis.OUTPUT_IMAGE_FORMAT_YUV_420_888)
            .setResolutionSelector(
                ResolutionSelector.Builder()
                    .setResolutionStrategy(ResolutionStrategy(Size(w, h), ResolutionStrategy.FALLBACK_RULE_NONE)).build(),
            )
        val ext = Camera2Interop.Extender(builder).setSessionCaptureCallback(recorder.captureCallback)
        if (fps != null) ext.setCaptureRequestOption(android.hardware.camera2.CaptureRequest.CONTROL_AE_TARGET_FPS_RANGE, android.util.Range(fps, fps))
        return builder.build()
    }

    private fun bindCamera() {
        provider.unbindAll()
        val preview = Preview.Builder().build().also { it.surfaceProvider = previewView.surfaceProvider }
        val analysis = buildAnalysis(res)
        analysis.setAnalyzer(analysisExecutor) { img ->
            try { recorder.onFrame(img) } finally { img.close() }
        }
        try {
            provider.bindToLifecycle(this, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
            status.text = "Ready, analysis $res"
        } catch (e: Exception) {
            status.text = "Bind failed: ${e.message}"
            Log.e(RunRecorder.TAG, "bind failed", e)
        }
    }

    private fun handleIntent() {
        if (intent.getBooleanExtra("bench", false)) {
            status.text = "Benchmark..."
            Thread {
                val f = Benchmark(this).run()
                Log.i(RunRecorder.TAG, "BENCH_DONE ${f.absolutePath}")
                main.post { status.text = "Benchmark done" }
            }.start()
        } else if (intent.getBooleanExtra("camera", false)) {
            startCameraBench()
        } else if (intent.hasExtra("video")) {
            startVideoRun(intent.getStringExtra("video")!!)
        } else if (intent.getBooleanExtra("probe", false)) {
            startProbe()
        } else if (intent.getBooleanExtra("autorun", false)) {
            startRun(intent.getIntExtra("seconds", 5), intent.getIntExtra("delay", 3))
        }
    }

    private fun startRun(seconds: Int, delay: Int) {
        if (busy) return
        busy = true
        recordButton.isEnabled = false
        fun tick(left: Int) {
            if (left > 0) {
                status.text = "Starting in $left s"
                main.postDelayed({ tick(left - 1) }, 1000)
                return
            }
            status.text = "Recording $seconds s at $res"
            recorder.start(res, seconds, arm, cap, liveMode, autoStopGroups, autoStop = {
                main.post { status.text = "Selecting frames (auto-stop)..."; recorder.stop() }
            }) { dir ->
                main.post { status.text = "Done: ${dir.name}"; busy = false; recordButton.isEnabled = true }
            }
            main.postDelayed({ status.text = "Selecting frames..."; recorder.stop() }, seconds * 1000L)
        }
        tick(delay)
    }

    /** Offline input: analyse video files instead of the camera. "video=all" takes every .mp4/.mov in files/in. */
    private fun startVideoRun(spec: String) {
        if (busy) return
        busy = true
        recordButton.isEnabled = false
        status.text = "Analysing video files..."
        Thread {
            val clips = if (spec == "all") {
                File(getExternalFilesDir(null), "in").listFiles { f -> f.extension.lowercase() in setOf("mp4", "mov") }
                    ?.sortedBy { it.name }?.map { it.absolutePath }.orEmpty()
            } else listOf(spec)
            val run = VideoRun(this)
            val decoder = intent.getStringExtra("decoder") ?: "retriever"
            val live = intent.getBooleanExtra("livepass", false)
            for (c in clips) {
                try {
                    val f = run.run(c, cap, decoder, live, intent.getIntExtra("maxreps", LiveSelector.DEFAULT_MAX_REPS), intent.getIntExtra("step", 1))
                    Log.i(RunRecorder.TAG, "VIDEO_DONE ${f.absolutePath}")
                } catch (e: Exception) {
                    Log.e(RunRecorder.TAG, "VIDEO_FAIL $c ${e}", e)
                }
            }
            Log.i(RunRecorder.TAG, "VIDEO_ALL_DONE ${clips.size}")
            main.post { status.text = "Video analysis done (${clips.size} clips)"; busy = false; recordButton.isEnabled = true }
        }.start()
    }

    private fun updateArmButton() {
        armButton.text = "Save frames of strategy: ${arm.label} (tap to change; all strategies are logged), cap $cap"
    }

    private fun startCameraBench() {
        if (busy) return
        busy = true
        status.text = "Camera-path benchmark..."
        CameraBench(this, this, provider, previewView) { l, f -> buildAnalysis(l, f) }.run { f ->
            main.post { status.text = "Camera benchmark done: ${f.name}"; busy = false; bindCamera() }
        }
    }

    private fun startProbe() {
        if (busy) return
        busy = true
        status.text = "Probing..."
        Probe(this, this, provider, previewView) { l -> buildAnalysis(l) }.run { f ->
            main.post { status.text = "Probe done: ${f.name}"; busy = false; bindCamera() }
        }
    }
}
