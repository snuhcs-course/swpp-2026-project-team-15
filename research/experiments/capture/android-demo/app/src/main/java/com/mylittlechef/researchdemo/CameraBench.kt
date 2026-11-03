// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
package com.mylittlechef.researchdemo

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageFormat
import android.graphics.Rect
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraDevice
import android.hardware.camera2.CameraManager
import android.hardware.camera2.CaptureRequest
import android.media.Image
import android.media.ImageReader
import android.media.MediaCodec
import android.media.MediaCodecInfo
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMetadataRetriever
import android.os.BatteryManager
import android.os.Build
import android.os.Debug
import android.os.Handler
import android.os.HandlerThread
import android.os.Looper
import android.os.PowerManager
import android.util.Log
import androidx.camera.camera2.interop.ExperimentalCamera2Interop
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.core.Preview
import androidx.camera.core.UseCase
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.video.FallbackStrategy
import androidx.camera.video.FileOutputOptions
import androidx.camera.video.Quality
import androidx.camera.video.QualitySelector
import androidx.camera.video.Recorder
import androidx.camera.video.VideoCapture
import androidx.camera.video.VideoRecordEvent
import androidx.camera.view.PreviewView
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleOwner
import org.json.JSONArray
import org.json.JSONObject
import org.opencv.core.Core
import org.opencv.core.CvType
import org.opencv.core.Mat
import org.opencv.core.Size
import org.opencv.imgproc.Imgproc
import java.io.ByteArrayOutputStream
import java.io.File
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit

/**
 * Camera-path measurements on the phone: how fast and how cheaply frames can be taken from the camera by each method.
 * Timing, throughput, memory and thermal numbers are valid for any scene. Compressed sizes, sharpness, keypoint counts
 * and anything that depends on image content are NOT representative when the camera sees a black or featureless scene;
 * those fields are listed under "content_dependent" and must not be read as results.
 *
 * Methods: (1) CameraX ImageAnalysis YUV stream, idle and with the full analysis; (2) per-operation conversion costs on
 * live frames (Y plane vs bitmap path, JPEG encode); (3) video recording then decode, MediaMetadataRetriever vs MediaCodec;
 * (4) repeated still capture (ImageCapture, minimum latency); (5) Camera2 burst and full-size YUV stream.
 */
@OptIn(ExperimentalCamera2Interop::class)
class CameraBench(
    private val ctx: Context,
    private val owner: LifecycleOwner,
    private val provider: ProcessCameraProvider,
    private val previewView: PreviewView,
    private val buildAnalysis: (String, Int?) -> ImageAnalysis,
) {
    private val main = Handler(Looper.getMainLooper())
    private val sel = CameraSelector.DEFAULT_BACK_CAMERA
    private val dir = File(ctx.getExternalFilesDir(null), "camera-bench").apply { mkdirs() }
    private val results = JSONObject()
    private val seconds = 6

    fun run(done: (File) -> Unit) {
        Thread {
            results.put("device", "${Build.MODEL} API ${Build.VERSION.SDK_INT}").put("opencv_version", Core.VERSION)
                .put("note", "timing/throughput/memory/thermal are valid; fields under content_dependent are not representative on a black scene")
            val f = File(ctx.getExternalFilesDir(null), "camera-bench.json")
            fun scenario(name: String, body: () -> JSONObject) {
                val before = snapshot()
                val r = try { body() } catch (e: Throwable) { Log.e(RunRecorder.TAG, "CAMBENCH $name failed", e); JSONObject().put("error", e.toString()) }
                r.put("state_before", before).put("state_after", snapshot())
                results.put(name, r)
                f.writeText(results.toString(2))
                Log.i(RunRecorder.TAG, "CAMBENCH $name done")
                Thread.sleep(800)
            }
            val exec = Executors.newSingleThreadExecutor()
            // fps = null: the camera's own auto-exposure choice (a dark scene slows it to 15 fps); 30 / 60: AE target fps range pinned
            for (fps in listOf<Int?>(null, 30)) for (res in listOf("640x480", "1280x720", "1920x1080")) {
                val tag = if (fps == null) "auto" else "fps$fps"
                scenario("stream_idle_${res}_$tag") { stream(res, false, exec, fps) }
                scenario("stream_pipeline_${res}_$tag") { stream(res, true, exec, fps) }
            }
            for (res in listOf("1280x720", "1920x1080")) {
                scenario("stream_idle_${res}_fps60") { stream(res, false, exec, 60) }
                scenario("stream_pipeline_${res}_fps60") { stream(res, true, exec, 60) }
            }
            for (rep in 1..2) for (res in listOf("1280x720", "1920x1080")) scenario("conversion_${res}_run$rep") { conversion(res) }
            scenario("video_FHD") { video(Quality.FHD, "FHD") }
            scenario("video_HD") { video(Quality.HD, "HD") }
            scenario("still_loop_alone") { stills(false) }
            scenario("still_loop_with_analysis") { stills(true) }
            scenario("camera2_burst_and_full_stream") { camera2() }
            exec.shutdownNow()
            onMain { provider.unbindAll() }
            results.put("finished", true)
            f.writeText(results.toString(2))
            Log.i(RunRecorder.TAG, "CAMBENCH_DONE ${f.absolutePath}")
            done(f)
        }.start()
    }

    // ---------- helpers ----------
    private fun <T> onMain(block: () -> T): T {
        var out: Result<T>? = null
        val latch = CountDownLatch(1)
        main.post { out = runCatching(block); latch.countDown() }
        latch.await(30, TimeUnit.SECONDS)
        return out!!.getOrThrow()
    }

    private fun bind(vararg cases: UseCase) = onMain {
        provider.unbindAll()
        provider.bindToLifecycle(owner, sel, *cases)
    }

    private fun previewCase() = onMain { Preview.Builder().build().also { it.surfaceProvider = previewView.surfaceProvider } }

    private fun snapshot(): JSONObject {
        val pm = ctx.getSystemService(Context.POWER_SERVICE) as PowerManager
        val mi = Debug.MemoryInfo(); Debug.getMemoryInfo(mi)
        val rt = Runtime.getRuntime()
        val bi: Intent? = ctx.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val temp = bi?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Int.MIN_VALUE) ?: Int.MIN_VALUE
        return JSONObject().put("thermal_status", pm.currentThermalStatus)
            .put("battery_temp_c", if (temp == Int.MIN_VALUE) JSONObject.NULL else temp / 10.0)
            .put("native_heap_mb", (Debug.getNativeHeapAllocatedSize() / 1048576.0).r2())
            .put("java_heap_mb", ((rt.totalMemory() - rt.freeMemory()) / 1048576.0).r2())
            .put("pss_total_mb", (mi.totalPss / 1024.0).r2())
    }

    private fun stats(v: List<Double>): JSONObject {
        val s = v.sorted().toDoubleArray()
        val o = JSONObject().put("n", s.size)
        if (s.isNotEmpty()) o.put("p50", Metrics.percentile(s, 50.0).r2()).put("p95", Metrics.percentile(s, 95.0).r2()).put("max", s.last().r2())
        return o
    }

    private fun Double.r2() = Math.round(this * 100) / 100.0

    private fun intervalStats(ts: List<Long>): JSONObject {
        val warm = ts.filter { it - ts.first() >= 1_000_000_000L } // first second discarded (auto-exposure settling)
        if (warm.size < 3) return JSONObject().put("frames", warm.size)
        val dts = warm.zipWithNext { a, b -> (b - a) / 1e6 }
        val span = (warm.last() - warm.first()) / 1e9
        return JSONObject().put("frames", warm.size).put("fps", ((warm.size - 1) / span).r2()).put("interval_ms", stats(dts))
    }

    // ---------- 1. CameraX analysis stream ----------
    private fun stream(res: String, pipeline: Boolean, exec: java.util.concurrent.ExecutorService, fps: Int?): JSONObject {
        val ts = ArrayList<Long>()
        val msY = ArrayList<Double>(); val msSharp = ArrayList<Double>(); val msOrb = ArrayList<Double>(); val msAll = ArrayList<Double>()
        val kp = ArrayList<Double>()
        val est = OverlapEstimator()
        var yBuf = ByteArray(0)
        val analysis = buildAnalysis(res, fps)
        analysis.setAnalyzer(exec) { img ->
            try {
                synchronized(ts) { ts.add(img.imageInfo.timestamp) }
                if (pipeline) {
                    val t0 = System.nanoTime()
                    val plane = img.planes[0]; val buf = plane.buffer; val need = buf.remaining()
                    if (yBuf.size < need) yBuf = ByteArray(need)
                    buf.get(yBuf, 0, need)
                    val t1 = System.nanoTime()
                    val small = Metrics.downscale(yBuf, plane.rowStride, img.width, img.height, 256)
                    Metrics.laplacianVariance(small); Metrics.meanBrightness(small)
                    val t2 = System.nanoTime()
                    val f = est.extract(Metrics.downscale(yBuf, plane.rowStride, img.width, img.height, OverlapEstimator.ORB_SIDE))
                    val t3 = System.nanoTime()
                    synchronized(ts) { msY.add((t1 - t0) / 1e6); msSharp.add((t2 - t1) / 1e6); msOrb.add((t3 - t2) / 1e6); msAll.add((t3 - t0) / 1e6); kp.add(f.count.toDouble()) }
                    f.release()
                }
            } finally { img.close() }
        }
        bind(previewCase(), analysis)
        Thread.sleep(seconds * 1000L)
        onMain { analysis.clearAnalyzer() }
        val actual = analysis.resolutionInfo?.resolution?.toString() ?: "n/a"
        val o = JSONObject().put("requested", res).put("actual", actual).put("target_fps_range", fps ?: JSONObject.NULL).put("pipeline", pipeline).put("seconds", seconds)
            .put("timing", intervalStats(synchronized(ts) { ts.toList() }))
        if (pipeline) {
            o.put("ms_y_copy", stats(msY)).put("ms_sharpness_256", stats(msSharp)).put("ms_orb_512", stats(msOrb)).put("ms_analyzer_total", stats(msAll))
            o.put("content_dependent", JSONObject().put("note", "ORB time scales with the number of keypoints; a black scene has almost none, so ms_orb_512 is a lower bound, not a result").put("keypoints_per_frame", stats(kp)))
        }
        return o
    }

    // ---------- 2. conversion costs on live frames ----------
    private fun conversion(res: String): JSONObject {
        val exec = Executors.newSingleThreadExecutor()
        val rows = HashMap<String, ArrayList<Double>>()
        val bytes = HashMap<String, ArrayList<Double>>()
        fun add(k: String, ms: Double) = rows.getOrPut(k) { ArrayList() }.add(ms)
        var count = 0
        val frames = 105
        var yBuf = ByteArray(0)
        val analysis = buildAnalysis(res, null)
        val latch = CountDownLatch(1)
        analysis.setAnalyzer(exec) { img ->
            try {
                count++
                if (count in 6..frames) {
                    val plane = img.planes[0]; val buf = plane.buffer; val need = buf.remaining()
                    if (yBuf.size < need) yBuf = ByteArray(need)
                    var t = System.nanoTime()
                    buf.get(yBuf, 0, need); add("y_plane_copy", ms(t))
                    t = System.nanoTime(); Metrics.downscale(yBuf, plane.rowStride, img.width, img.height, 256); add("y_downscale_256_kotlin", ms(t))
                    t = System.nanoTime(); Metrics.downscale(yBuf, plane.rowStride, img.width, img.height, 512); add("y_downscale_512_kotlin", ms(t))
                    // OpenCV path on the same Y plane
                    t = System.nanoTime()
                    val m = Mat(img.height, plane.rowStride, CvType.CV_8UC1); m.put(0, 0, yBuf.copyOf(plane.rowStride * img.height))
                    val sub = m.submat(0, img.height, 0, img.width)
                    val sc = 256.0 / maxOf(img.width, img.height)
                    val dst = Mat(); Imgproc.resize(sub, dst, Size(Math.round(img.width * sc).toDouble(), Math.round(img.height * sc).toDouble()), 0.0, 0.0, Imgproc.INTER_AREA)
                    add("y_downscale_256_opencv_resize_area", ms(t)); dst.release(); sub.release(); m.release()
                    // the earlier "bitmap path": ImageProxy -> Bitmap -> luma -> downscale
                    t = System.nanoTime(); val bmp = img.toBitmap(); val tb = ms(t); add("bitmap_path_toBitmap", tb)
                    t = System.nanoTime()
                    val bw = bmp.width; val bh = bmp.height
                    val px = IntArray(bw * bh); bmp.getPixels(px, 0, bw, 0, 0, bw, bh)
                    val y = ByteArray(bw * bh)
                    for (i in px.indices) { val p = px[i]; y[i] = ((77 * ((p shr 16) and 255) + 150 * ((p shr 8) and 255) + 29 * (p and 255) + 128) shr 8).toByte() }
                    Metrics.downscale(y, bw, bw, bh, 256)
                    add("bitmap_path_luma_and_downscale", ms(t)); bmp.recycle()
                    // NV21 + JPEG
                    t = System.nanoTime(); val (n1024, w1, h1) = nv21(img, yBuf, 1024); add("nv21_build_1024", ms(t))
                    val o1 = ByteArrayOutputStream()
                    t = System.nanoTime(); android.graphics.YuvImage(n1024, ImageFormat.NV21, w1, h1, null).compressToJpeg(Rect(0, 0, w1, h1), 85, o1); add("jpeg_encode_1024_q85", ms(t))
                    bytes.getOrPut("jpeg_bytes_1024_q85") { ArrayList() }.add(o1.size().toDouble())
                    t = System.nanoTime(); val (nf, wf, hf) = nv21(img, yBuf, maxOf(img.width, img.height)); add("nv21_build_full", ms(t))
                    val o2 = ByteArrayOutputStream()
                    t = System.nanoTime(); android.graphics.YuvImage(nf, ImageFormat.NV21, wf, hf, null).compressToJpeg(Rect(0, 0, wf, hf), 90, o2); add("jpeg_encode_full_frame_q90", ms(t))
                    bytes.getOrPut("jpeg_bytes_full_frame_q90") { ArrayList() }.add(o2.size().toDouble())
                }
                if (count == frames) latch.countDown()
            } finally { img.close() }
        }
        bind(previewCase(), analysis)
        latch.await(40, TimeUnit.SECONDS)
        onMain { analysis.clearAnalyzer() }
        exec.shutdownNow()
        val o = JSONObject().put("requested", res).put("actual", analysis.resolutionInfo?.resolution?.toString() ?: "n/a").put("frames_measured", frames - 5)
        for ((k, v) in rows) o.put("ms_$k", stats(v))
        o.put("content_dependent", JSONObject().put("note", "JPEG sizes depend on image content; a black scene compresses far below real scenes").also { c -> for ((k, v) in bytes) c.put(k, stats(v)) })
        return o
    }

    private fun ms(t: Long) = (System.nanoTime() - t) / 1e6

    /** NV21 copy of an analysis frame whose long side is at most [longSide] (nearest sampling, like the app's saved frames). */
    private fun nv21(img: ImageProxy, yBuf: ByteArray, longSide: Int): Triple<ByteArray, Int, Int> {
        val w = img.width; val h = img.height
        val scale = minOf(1.0, longSide.toDouble() / maxOf(w, h))
        val ow = (Math.round(w * scale).toInt() / 2) * 2; val oh = (Math.round(h * scale).toInt() / 2) * 2
        val out = ByteArray(ow * oh * 3 / 2)
        val yRow = img.planes[0].rowStride
        val xs = IntArray(ow) { it * w / ow }
        for (yy in 0 until oh) { val row = (yy * h / oh) * yRow; val o = yy * ow; for (xx in 0 until ow) out[o + xx] = yBuf[row + xs[xx]] }
        val u = img.planes[1]; val v = img.planes[2]
        val ub = ByteArray(u.buffer.remaining()).also { u.buffer.get(it) }; val vb = ByteArray(v.buffer.remaining()).also { v.buffer.get(it) }
        var o = ow * oh
        val cxs = IntArray(ow / 2) { ((it * 2 * w / ow) / 2) * u.pixelStride }
        for (cy in 0 until oh / 2) {
            val ur = ((cy * 2 * h / oh) / 2) * u.rowStride; val vr = ((cy * 2 * h / oh) / 2) * v.rowStride
            for (cx in 0 until ow / 2) { out[o++] = vb[vr + cxs[cx]]; out[o++] = ub[ur + cxs[cx]] }
        }
        u.buffer.rewind(); v.buffer.rewind()
        return Triple(out, ow, oh)
    }

    // ---------- 3. video record then decode ----------
    private fun video(q: Quality, label: String): JSONObject {
        val file = File(dir, "rec_$label.mp4").apply { delete() }
        val recorder = Recorder.Builder().setQualitySelector(QualitySelector.from(q, FallbackStrategy.lowerQualityOrHigherThan(q))).build()
        val vc = VideoCapture.withOutput(recorder)
        bind(previewCase(), vc)
        Thread.sleep(1200)
        val startLatch = CountDownLatch(1); val finLatch = CountDownLatch(1)
        var tReq = 0L; var tStart = 0L; var tFin = 0L; var tStop = 0L; var err = -1; var bytesRec = 0L
        val rec = onMain {
            tReq = System.nanoTime()
            recorder.prepareRecording(ctx, FileOutputOptions.Builder(file).build()).start(ContextCompat.getMainExecutor(ctx)) { e ->
                when (e) {
                    is VideoRecordEvent.Start -> { tStart = System.nanoTime(); startLatch.countDown() }
                    is VideoRecordEvent.Finalize -> { tFin = System.nanoTime(); err = e.error; finLatch.countDown() }
                    is VideoRecordEvent.Status -> bytesRec = e.recordingStats.numBytesRecorded
                    else -> {}
                }
            }
        }
        startLatch.await(10, TimeUnit.SECONDS)
        Thread.sleep(seconds * 1000L)
        onMain { tStop = System.nanoTime(); rec.stop() }
        finLatch.await(15, TimeUnit.SECONDS)
        val o = JSONObject().put("quality", label).put("record_seconds", seconds).put("finalize_error_code", err)
            .put("start_latency_ms", ((tStart - tReq) / 1e6).r2()).put("finalize_ms_after_stop", ((tFin - tStop) / 1e6).r2())
            .put("file_bytes", file.length())
        if (!file.exists() || file.length() == 0L) return o.put("error", "no file")
        // container facts
        val ex = MediaExtractor(); ex.setDataSource(file.absolutePath)
        val track = (0 until ex.trackCount).first { ex.getTrackFormat(it).getString(MediaFormat.KEY_MIME)!!.startsWith("video/") }
        val fmt = ex.getTrackFormat(track)
        ex.selectTrack(track)
        var samples = 0; var first = -1L; var last = 0L
        while (ex.sampleTime >= 0) { if (first < 0) first = ex.sampleTime; last = ex.sampleTime; samples++; if (!ex.advance()) break }
        ex.release()
        val durS = (last - first) / 1e6
        o.put("width", fmt.getInteger(MediaFormat.KEY_WIDTH)).put("height", fmt.getInteger(MediaFormat.KEY_HEIGHT))
            .put("samples", samples).put("fps_in_file", if (durS > 0) ((samples - 1) / durS).r2() else JSONObject.NULL)
        // decode 1: MediaMetadataRetriever (what the video-file mode used)
        val mmr = MediaMetadataRetriever(); mmr.setDataSource(file.absolutePath)
        val per = ArrayList<Double>(); val n = minOf(60, samples)
        val tAll = System.nanoTime()
        for (i in 0 until n) { val t = System.nanoTime(); mmr.getFrameAtIndex(i)?.recycle(); per.add(ms(t)) }
        val wallRetriever = ms(tAll); mmr.release()
        o.put("decode_retriever_first_${n}_frames", JSONObject().put("ms_per_frame", stats(per)).put("frames_per_s", (n / (wallRetriever / 1000.0)).r2()))
        // decode 2: MediaCodec to YUV images, Y plane copied and reduced like a camera frame
        o.put("decode_mediacodec_all_frames", CodecDecoder.decodeStats(file.absolutePath))
        file.delete()
        o.put("content_dependent", JSONObject().put("file_bytes_note", "bitrate and file size depend on image content; a black scene is far smaller than real footage"))
        return o
    }

    // ---------- 4. repeated still capture ----------
    private fun stills(withAnalysis: Boolean): JSONObject {
        val cap = onMain { ImageCapture.Builder().setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY).build() }
        val analysisTs = ArrayList<Long>()
        val cases = ArrayList<UseCase>(); cases += previewCase(); cases += cap
        val exec = Executors.newSingleThreadExecutor()
        if (withAnalysis) {
            val a = buildAnalysis("1280x720", null)
            a.setAnalyzer(exec) { img -> synchronized(analysisTs) { analysisTs.add(img.imageInfo.timestamp) }; img.close() }
            cases += a
        }
        bind(*cases.toTypedArray())
        Thread.sleep(1500)
        val lat = ArrayList<Double>(); val sizes = ArrayList<Double>(); var dims = ""
        val jpegs = ArrayList<ByteArray>()
        val t0 = System.nanoTime()
        var errors = 0
        while (ms(t0) < 8000) {
            val latch = CountDownLatch(1)
            val t = System.nanoTime()
            onMain {
                cap.takePicture(exec, object : ImageCapture.OnImageCapturedCallback() {
                    override fun onCaptureSuccess(image: ImageProxy) {
                        lat.add(ms(t)); dims = "${image.width}x${image.height}"
                        val b = image.planes[0].buffer; val arr = ByteArray(b.remaining()); b.get(arr)
                        sizes.add(arr.size.toDouble()); if (jpegs.size < 3) jpegs.add(arr)
                        image.close(); latch.countDown()
                    }
                    override fun onError(e: ImageCaptureException) { errors++; latch.countDown() }
                })
            }
            if (!latch.await(10, TimeUnit.SECONDS)) { errors++; break }
        }
        val wall = ms(t0) / 1000.0
        val o = JSONObject().put("with_analysis_1280x720", withAnalysis).put("mode", "MINIMIZE_LATENCY").put("size", dims)
            .put("captures", lat.size).put("errors", errors).put("stills_per_s", (lat.size / wall).r2()).put("latency_ms", stats(lat))
        if (withAnalysis) o.put("analysis_during_stills", intervalStats(synchronized(analysisTs) { analysisTs.toList() }))
        // JPEG -> the two upload sizes
        val conv = JSONObject()
        val dec = ArrayList<Double>(); val r1024 = ArrayList<Double>(); val r2048 = ArrayList<Double>()
        for (j in jpegs) {
            for ((longSide, q, sink) in listOf(Triple(1024, 85, r1024), Triple(2048, 90, r2048))) {
                val t = System.nanoTime()
                val opt = BitmapFactory.Options().apply { inJustDecodeBounds = true }; BitmapFactory.decodeByteArray(j, 0, j.size, opt)
                var sample = 1; while (maxOf(opt.outWidth, opt.outHeight) / (sample * 2) >= longSide) sample *= 2
                val bmp = BitmapFactory.decodeByteArray(j, 0, j.size, BitmapFactory.Options().apply { inSampleSize = sample })
                val sc = longSide.toDouble() / maxOf(bmp.width, bmp.height)
                val scaled = Bitmap.createScaledBitmap(bmp, Math.round(bmp.width * sc).toInt(), Math.round(bmp.height * sc).toInt(), true)
                val out = ByteArrayOutputStream(); scaled.compress(Bitmap.CompressFormat.JPEG, q, out)
                sink.add(ms(t)); if (scaled !== bmp) scaled.recycle(); bmp.recycle()
            }
        }
        conv.put("ms_jpeg_decode_resize_encode_to_1024_q85", stats(r1024)).put("ms_jpeg_decode_resize_encode_to_2048_q90", stats(r2048)).put("frames", jpegs.size)
        o.put("resize_from_still", conv)
        o.put("content_dependent", JSONObject().put("still_jpeg_bytes", stats(sizes)).put("note", "JPEG size of a black scene is far below real scenes"))
        if (withAnalysis) onMain { }
        exec.shutdownNow()
        return o
    }

    // ---------- 5. Camera2: burst and full-size stream ----------
    @Suppress("DEPRECATION")
    private fun camera2(): JSONObject {
        onMain { provider.unbindAll() }
        Thread.sleep(1500)
        val o = JSONObject()
        val mgr = ctx.getSystemService(Context.CAMERA_SERVICE) as CameraManager
        val id = "0"
        val ch = mgr.getCameraCharacteristics(id)
        val map = ch.get(CameraCharacteristics.SCALER_STREAM_CONFIGURATION_MAP)!!
        fun largest(fmt: Int, maxW: Int): android.util.Size = map.getOutputSizes(fmt).filter { it.width <= maxW && it.width * 3 == it.height * 4 }.maxByOrNull { it.width * it.height }!!
        val jpeg = largest(ImageFormat.JPEG, 4000); val yuvBig = largest(ImageFormat.YUV_420_888, 4000)
        o.put("jpeg_size", jpeg.toString()).put("yuv_big_size", yuvBig.toString())
        val ht = HandlerThread("cam2").also { it.start() }
        val h = Handler(ht.looper)
        val opened = CountDownLatch(1); var dev: CameraDevice? = null
        ctx.checkSelfPermission(android.Manifest.permission.CAMERA)
        @Suppress("MissingPermission")
        mgr.openCamera(id, object : CameraDevice.StateCallback() {
            override fun onOpened(c: CameraDevice) { dev = c; opened.countDown() }
            override fun onDisconnected(c: CameraDevice) { c.close() }
            override fun onError(c: CameraDevice, e: Int) { o.put("open_error", e); opened.countDown() }
        }, h)
        opened.await(10, TimeUnit.SECONDS)
        val d = dev ?: return o.put("error", "camera not opened")
        try {
            fun session(reader: ImageReader): CameraCaptureSession {
                val l = CountDownLatch(1); var s: CameraCaptureSession? = null
                d.createCaptureSession(listOf(reader.surface), object : CameraCaptureSession.StateCallback() {
                    override fun onConfigured(x: CameraCaptureSession) { s = x; l.countDown() }
                    override fun onConfigureFailed(x: CameraCaptureSession) { l.countDown() }
                }, h)
                l.await(10, TimeUnit.SECONDS)
                return s ?: error("session configure failed")
            }
            // burst of N JPEG stills
            for (n in intArrayOf(8, 15)) {
                val arrivals = java.util.Collections.synchronizedList(ArrayList<Long>())
                val reader = ImageReader.newInstance(jpeg.width, jpeg.height, ImageFormat.JPEG, n + 2)
                reader.setOnImageAvailableListener({ r -> r.acquireNextImage()?.let { im -> arrivals.add(System.nanoTime()); im.close() } }, h)
                val s = session(reader)
                val reqs = List(n) {
                    d.createCaptureRequest(CameraDevice.TEMPLATE_STILL_CAPTURE).apply {
                        addTarget(reader.surface); set(CaptureRequest.JPEG_QUALITY, 90.toByte())
                    }.build()
                }
                val t0 = System.nanoTime()
                s.captureBurst(reqs, null, h)
                val deadline = System.nanoTime() + 25_000_000_000L
                while (arrivals.size < n && System.nanoTime() < deadline) Thread.sleep(20)
                val a = synchronized(arrivals) { arrivals.toList() }
                val gaps = a.zipWithNext { x, y -> (y - x) / 1e6 }
                o.put("burst_$n", JSONObject().put("requested", n).put("received", a.size)
                    .put("ms_until_first", if (a.isNotEmpty()) ((a.first() - t0) / 1e6).r2() else JSONObject.NULL)
                    .put("ms_until_last", if (a.isNotEmpty()) ((a.last() - t0) / 1e6).r2() else JSONObject.NULL)
                    .put("stills_per_s", if (a.size > 1) ((a.size - 1) / ((a.last() - a.first()) / 1e9)).r2() else JSONObject.NULL)
                    .put("gap_ms", stats(gaps)))
                s.close(); reader.close(); Thread.sleep(500)
            }
            // repeating YUV stream at full size and at 1920x1080
            for (size in listOf(yuvBig, android.util.Size(1920, 1080))) {
                val stamps = java.util.Collections.synchronizedList(ArrayList<Long>())
                val reader = ImageReader.newInstance(size.width, size.height, ImageFormat.YUV_420_888, 4)
                reader.setOnImageAvailableListener({ r -> r.acquireLatestImage()?.let { im -> stamps.add(im.timestamp); im.close() } }, h)
                try {
                    val s = session(reader)
                    val rq = d.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW).apply { addTarget(reader.surface) }.build()
                    s.setRepeatingRequest(rq, null, h)
                    Thread.sleep(5000)
                    s.stopRepeating(); s.close()
                    o.put("yuv_stream_${size.width}x${size.height}", intervalStats(synchronized(stamps) { stamps.toList() }))
                } catch (e: Exception) {
                    o.put("yuv_stream_${size.width}x${size.height}", JSONObject().put("error", e.toString()))
                }
                reader.close(); Thread.sleep(500)
            }
        } finally {
            d.close(); ht.quitSafely()
        }
        o.put("content_dependent", JSONObject().put("note", "none of these fields depend on image content except compressed sizes, which are not reported"))
        return o
    }
}

/** MediaCodec decode of a whole video file to YUV images (no bitmap, no per-frame seek). */
object CodecDecoder {
    /** Calls [onFrame] (index, presentation time in ns, Y plane bytes, row stride, width, height) for every frame in display order.
     *  The Y array is reused between calls. Frames are not rotated (the container's rotation flag is ignored). */
    fun forEachFrame(path: String, onFrame: (Int, Long, ByteArray, Int, Int, Int) -> Unit): Int {
        val ex = MediaExtractor(); ex.setDataSource(path)
        val track = (0 until ex.trackCount).first { ex.getTrackFormat(it).getString(MediaFormat.KEY_MIME)!!.startsWith("video/") }
        val fmt = ex.getTrackFormat(track); ex.selectTrack(track)
        val codec = MediaCodec.createDecoderByType(fmt.getString(MediaFormat.KEY_MIME)!!)
        fmt.setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatYUV420Flexible)
        codec.configure(fmt, null, null, 0); codec.start()
        val info = MediaCodec.BufferInfo()
        var inDone = false; var outDone = false; var frames = 0
        var yBuf = ByteArray(0)
        try {
            while (!outDone) {
                if (!inDone) {
                    val ib = codec.dequeueInputBuffer(5000)
                    if (ib >= 0) {
                        val n = ex.readSampleData(codec.getInputBuffer(ib)!!, 0)
                        if (n < 0) { codec.queueInputBuffer(ib, 0, 0, 0, MediaCodec.BUFFER_FLAG_END_OF_STREAM); inDone = true }
                        else { codec.queueInputBuffer(ib, 0, n, ex.sampleTime, 0); ex.advance() }
                    }
                }
                val ob = codec.dequeueOutputBuffer(info, 5000)
                if (ob >= 0) {
                    val eos = info.flags and MediaCodec.BUFFER_FLAG_END_OF_STREAM != 0
                    if (info.size > 0) {
                        val img: Image? = codec.getOutputImage(ob)
                        if (img != null) {
                            val p = img.planes[0]; val b = p.buffer; val need = b.remaining()
                            if (yBuf.size < need) yBuf = ByteArray(need)
                            b.get(yBuf, 0, need)
                            onFrame(frames, info.presentationTimeUs * 1000L, yBuf, p.rowStride, img.width, img.height)
                            img.close(); frames++
                        }
                    }
                    codec.releaseOutputBuffer(ob, false)
                    if (eos) outDone = true
                }
            }
        } finally {
            codec.stop(); codec.release(); ex.release()
        }
        return frames
    }

    fun decodeStats(path: String): JSONObject {
        val perFrame = ArrayList<Double>(); val yMs = ArrayList<Double>()
        val t0 = System.nanoTime(); var last = t0
        val frames = forEachFrame(path) { _, _, y, rs, w, h ->
            val ty = System.nanoTime()
            Metrics.downscale(y, rs, w, h, 256)
            yMs.add((System.nanoTime() - ty) / 1e6)
            val now = System.nanoTime(); perFrame.add((now - last) / 1e6); last = now
        }
        val wall = (System.nanoTime() - t0) / 1e6
        fun st(v: List<Double>): JSONObject { val s = v.sorted().toDoubleArray(); return JSONObject().put("n", s.size).put("p50", Math.round(Metrics.percentile(s, 50.0) * 100) / 100.0).put("p95", Math.round(Metrics.percentile(s, 95.0) * 100) / 100.0) }
        return JSONObject().put("frames", frames).put("wall_ms", Math.round(wall * 10) / 10.0)
            .put("frames_per_s", Math.round(frames / (wall / 1000.0) * 100) / 100.0)
            .put("ms_between_frames", st(perFrame)).put("ms_y_copy_and_downscale_256", st(yMs))
    }
}
