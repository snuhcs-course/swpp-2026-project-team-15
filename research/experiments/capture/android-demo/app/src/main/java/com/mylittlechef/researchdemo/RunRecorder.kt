// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; reviewed by Jaehyuk Choi.
package com.mylittlechef.researchdemo

import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.ImageFormat
import android.graphics.Rect
import android.hardware.camera2.CameraCaptureSession
import android.hardware.camera2.CaptureRequest
import android.hardware.camera2.CaptureResult
import android.hardware.camera2.TotalCaptureResult
import android.media.ExifInterface
import android.os.BatteryManager
import android.os.PowerManager
import android.util.Log
import androidx.camera.core.ImageProxy
import org.json.JSONArray
import org.json.JSONObject
import org.opencv.core.Core
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ExecutorService
import java.util.concurrent.Executors
import java.util.concurrent.atomic.AtomicInteger

/** Per-frame capture metadata from the Camera2 capture result (null = the phone did not report the key). */
data class Meta(
    val exposureNs: Long?, val iso: Int?, val frameDurationNs: Long?, val focusDistance: Float?,
    val lensState: Int?, val afState: Int?, val aeState: Int?,
)

class FrameRec(
    val ts: Long, val sharp: Double, val bright: Double, val msSharp: Double, val msOrb: Double, val msSpool: Double,
    val feat: Features, val rotation: Int, val spoolW: Int, val spoolH: Int,
) {
    var meta: Meta? = null
    var kept = false
    var groupId = -1
    var chosen = false
    val inArm = BooleanArray(Arm.entries.size)
    var overlapToAnchor: Float? = null
    var reliable: Boolean? = null
    var msMatch: Double? = null
}

/** Records one clip: per-frame metrics online, selection (gate, groups, cap) after the clip ends. */
class RunRecorder(private val ctx: Context, private val executor: ExecutorService) {
    @Volatile var active = false
        private set

    private val estimator = OverlapEstimator()
    private var spoolExecutor = Executors.newSingleThreadExecutor()
    private val metas = ConcurrentHashMap<Long, Meta>()
    private val resultCount = AtomicInteger()
    private val frames = ArrayList<FrameRec>()
    private var yBuf = ByteArray(0)
    private lateinit var runDir: File
    private lateinit var spoolDir: File
    private var width = 0
    private var height = 0
    private var resLabel = ""
    private var requestedSeconds = 0
    private var saveArm = Arm.OVERLAP
    private var cap = ArmSelector.MIN_CAP
    private val armStats = JSONObject()
    private var startedAtNs = 0L
    private var thermalStart = -1
    private var batteryStart = Double.NaN
    private var onDone: (File) -> Unit = {}

    /** OFF: offline strategies only. WITH_OFFLINE: the streaming selector runs next to the offline strategies on the same frames
     *  (parity check, memory not bounded). ONLY: just the streaming selector (bounded memory, the real live path). */
    enum class LiveMode { OFF, WITH_OFFLINE, ONLY;
        companion object { fun parse(t: String?) = entries.firstOrNull { it.name.equals(t, true) || (t == "with" && it == WITH_OFFLINE) } ?: OFF }
    }
    private var liveMode = LiveMode.OFF
    private var live: LiveSelector? = null
    private val liveFeats = HashMap<Int, Features>()
    private var liveIdx = 0
    private val livePairCache = HashMap<Long, Overlap>()
    private val livePairLog = ArrayList<DoubleArray>() // [a, b, value, reliable(1/0), ms]
    private val livePushMs = ArrayList<Double>()
    private val liveRows = ArrayList<DoubleArray>() // [index, ts_ns, sharpness, gate(1/0), ms_sharp, ms_orb, ms_push, ms_spool]
    private val liveSpoolDims = HashMap<Int, IntArray>() // idx -> [w, h, rotation]
    private val memSamples = ArrayList<DoubleArray>() // [t_s, native_heap_mb, java_heap_mb]
    private var liveFinishMs = 0.0
    private var autoStopGroups = 0
    private var autoStopped = false
    private var onAutoStop: (() -> Unit)? = null
    private val finishing = java.util.concurrent.atomic.AtomicBoolean(false)

    val captureCallback = object : CameraCaptureSession.CaptureCallback() {
        override fun onCaptureCompleted(session: CameraCaptureSession, request: CaptureRequest, result: TotalCaptureResult) {
            if (!active) return
            val ts = result.get(CaptureResult.SENSOR_TIMESTAMP) ?: return
            resultCount.incrementAndGet()
            metas[ts] = Meta(
                result.get(CaptureResult.SENSOR_EXPOSURE_TIME), result.get(CaptureResult.SENSOR_SENSITIVITY),
                result.get(CaptureResult.SENSOR_FRAME_DURATION), result.get(CaptureResult.LENS_FOCUS_DISTANCE),
                result.get(CaptureResult.LENS_STATE), result.get(CaptureResult.CONTROL_AF_STATE),
                result.get(CaptureResult.CONTROL_AE_STATE),
            )
        }
    }

    /** [arm] picks which strategy's frames are saved as JPEG; every strategy's choice is computed and logged for the same clip. */
    fun start(
        res: String, seconds: Int, arm: Arm, cap: Int, mode: LiveMode = LiveMode.OFF, autoStopAtGroups: Int = 0,
        autoStop: (() -> Unit)? = null, done: (File) -> Unit,
    ) {
        saveArm = arm; this.cap = ArmSelector.clampCap(cap)
        liveMode = mode; autoStopGroups = autoStopAtGroups; onAutoStop = autoStop; autoStopped = false; finishing.set(false)
        liveFeats.clear(); liveIdx = 0; livePairCache.clear(); livePairLog.clear(); livePushMs.clear(); liveRows.clear()
        liveSpoolDims.clear(); memSamples.clear()
        live = if (mode != LiveMode.OFF) LiveSelector(this.cap, pair = { a, b -> livePair(a, b) }, release = { releaseLive(it) }) else null
        val stamp = SimpleDateFormat("yyyyMMdd-HHmmss", Locale.US).format(Date())
        runDir = File(ctx.getExternalFilesDir(null), "runs/${stamp}_$res").apply { mkdirs() }
        spoolDir = File(ctx.cacheDir, "spool").apply { deleteRecursively(); mkdirs() }
        frames.clear(); metas.clear(); resultCount.set(0)
        spoolExecutor = Executors.newSingleThreadExecutor()
        resLabel = res; requestedSeconds = seconds; onDone = done
        thermalStart = thermal(); batteryStart = batteryTempC()
        startedAtNs = System.nanoTime()
        active = true
    }

    fun stop() {
        if (!finishing.compareAndSet(false, true)) return
        active = false
        // The analysis executor is single-threaded, so frames already queued finish before finish() runs.
        executor.execute { finish() }
    }

    /** Called on the analysis executor for every frame; does not close the image. */
    fun onFrame(image: ImageProxy) {
        if (!active) return
        val t0 = System.nanoTime()
        width = image.width; height = image.height
        val plane = image.planes[0]
        val buf = plane.buffer
        val need = buf.remaining()
        if (yBuf.size < need) yBuf = ByteArray(need)
        buf.get(yBuf, 0, need)
        val small = Metrics.downscale(yBuf, plane.rowStride, image.width, image.height, 256)
        val sharp = Metrics.laplacianVariance(small)
        val bright = Metrics.meanBrightness(small)
        val t1 = System.nanoTime()
        val feat = estimator.extract(Metrics.downscale(yBuf, plane.rowStride, image.width, image.height, OverlapEstimator.ORB_SIDE))
        val t2 = System.nanoTime()
        if (liveMode == LiveMode.ONLY) { onFrameLiveOnly(image, t0, t1, t2, sharp, feat); return }
        val idx = frames.size
        val (nv21, sw, sh) = spoolImage(image)
        val t3 = System.nanoTime()
        spoolExecutor.execute { File(spoolDir, "$idx.nv21").writeBytes(nv21) }
        frames.add(
            FrameRec(
                image.imageInfo.timestamp, sharp, bright, (t1 - t0) / 1e6, (t2 - t1) / 1e6, (t3 - t2) / 1e6,
                feat, image.imageInfo.rotationDegrees, sw, sh,
            ),
        )
        if (liveMode == LiveMode.WITH_OFFLINE) {
            liveFeats[idx] = feat
            val tp = System.nanoTime()
            val pass = live!!.push(idx, image.imageInfo.timestamp, sharp)
            val ms = (System.nanoTime() - tp) / 1e6
            livePushMs.add(ms)
            liveRows.add(doubleArrayOf(idx.toDouble(), image.imageInfo.timestamp.toDouble(), sharp, if (pass) 1.0 else 0.0, (t1 - t0) / 1e6, (t2 - t1) / 1e6, ms, 0.0))
            sampleMemory()
            checkAutoStop()
        }
    }

    /** The real live path: no frame list, features and pixels are kept only for the frames the selector still holds. */
    private fun onFrameLiveOnly(image: ImageProxy, t0: Long, t1: Long, t2: Long, sharp: Double, feat: Features) {
        val idx = liveIdx++
        val tsNs = image.imageInfo.timestamp
        liveFeats[idx] = feat
        val tp = System.nanoTime()
        val pass = live!!.push(idx, tsNs, sharp)
        val tq = System.nanoTime()
        var msSpool = 0.0
        if (live!!.isHeld(idx)) {
            val (nv21, sw, sh) = spoolImage(image)
            File(spoolDir, "$idx.nv21").writeBytes(nv21)
            liveSpoolDims[idx] = intArrayOf(sw, sh, image.imageInfo.rotationDegrees)
            msSpool = (System.nanoTime() - tq) / 1e6
        }
        val msPush = (tq - tp) / 1e6
        livePushMs.add(msPush)
        liveRows.add(doubleArrayOf(idx.toDouble(), tsNs.toDouble(), sharp, if (pass) 1.0 else 0.0, (t1 - t0) / 1e6, (t2 - t1) / 1e6, msPush, msSpool))
        sampleMemory()
        checkAutoStop()
    }

    private fun checkAutoStop() {
        if (autoStopGroups > 0 && !autoStopped && live!!.groupsClosed >= autoStopGroups) {
            autoStopped = true
            onAutoStop?.invoke()
        }
    }

    private fun sampleMemory() {
        if (liveRows.size % 10 != 1) return
        val rt = Runtime.getRuntime()
        memSamples.add(doubleArrayOf((System.nanoTime() - startedAtNs) / 1e9, android.os.Debug.getNativeHeapAllocatedSize() / 1048576.0, (rt.totalMemory() - rt.freeMemory()) / 1048576.0))
    }

    private fun livePair(a: Int, b: Int): Overlap = livePairCache.getOrPut(a.toLong() * 1_000_000 + b) {
        val (ow, oh) = orbShape()
        val t = System.nanoTime()
        val o = estimator.overlap(liveFeats.getValue(a), liveFeats.getValue(b), ow, oh)
        livePairLog.add(doubleArrayOf(a.toDouble(), b.toDouble(), o.value.toDouble(), if (o.reliable) 1.0 else 0.0, (System.nanoTime() - t) / 1e6))
        o
    }

    private fun releaseLive(i: Int) {
        val f = liveFeats.remove(i)
        if (liveMode == LiveMode.ONLY) {
            f?.release()
            File(spoolDir, "$i.nv21").delete()
            liveSpoolDims.remove(i)
        }
    }

    /** NV21 copy at <= 1024 px long side (nearest sampling) kept on disk so chosen frames can be saved as JPEG later. */
    private var uArr = ByteArray(0)
    private var vArr = ByteArray(0)

    private fun copyPlane(p: ImageProxy.PlaneProxy, into: ByteArray): ByteArray {
        val b = p.buffer
        val arr = if (into.size >= b.remaining()) into else ByteArray(b.remaining())
        b.get(arr, 0, b.remaining())
        return arr
    }

    private fun spoolImage(image: ImageProxy): Triple<ByteArray, Int, Int> {
        val w = image.width; val h = image.height
        val scale = minOf(1.0, 1024.0 / maxOf(w, h))
        val ow = (Math.round(w * scale).toInt() / 2) * 2
        val oh = (Math.round(h * scale).toInt() / 2) * 2
        val out = ByteArray(ow * oh * 3 / 2)
        val yRow = image.planes[0].rowStride
        val xs = IntArray(ow) { it * w / ow }
        for (yy in 0 until oh) {
            val row = (yy * h / oh) * yRow
            val o = yy * ow
            for (xx in 0 until ow) out[o + xx] = yBuf[row + xs[xx]]
        }
        val u = image.planes[1]; val v = image.planes[2]
        uArr = copyPlane(u, uArr); vArr = copyPlane(v, vArr)
        var o = ow * oh
        val cxs = IntArray(ow / 2) { ((it * 2 * w / ow) / 2) * u.pixelStride }
        for (cy in 0 until oh / 2) {
            val ur = ((cy * 2 * h / oh) / 2) * u.rowStride
            val vr = ((cy * 2 * h / oh) / 2) * v.rowStride
            for (cx in 0 until ow / 2) {
                out[o++] = vArr[vr + cxs[cx]]
                out[o++] = uArr[ur + cxs[cx]]
            }
        }
        return Triple(out, ow, oh)
    }

    private fun finish() {
        Thread.sleep(400) // let the last capture results arrive
        spoolExecutor.shutdown(); spoolExecutor.awaitTermination(20, java.util.concurrent.TimeUnit.SECONDS)
        if (liveMode == LiveMode.ONLY) { finishLiveOnly(); return }
        if (frames.isEmpty()) {
            File(runDir, "summary.json").writeText("""{"error":"no frames analyzed"}""")
            onDone(runDir); return
        }
        joinMetadata()
        val (ow, oh) = orbShape()
        val pairCache = HashMap<Long, Overlap>()
        val pairMs = ArrayList<Double>()
        var lastMs = 0.0
        val pair = { a: Int, b: Int ->
            pairCache.getOrPut(a.toLong() * 1_000_000 + b) {
                val t = System.nanoTime()
                val o = estimator.overlap(frames[a].feat, frames[b].feat, ow, oh)
                lastMs = (System.nanoTime() - t) / 1e6
                pairMs.add(lastMs)
                o
            }
        }
        val sharp = DoubleArray(frames.size) { frames[it].sharp }
        val tsArr = LongArray(frames.size) { frames[it].ts }
        var groupCount = 0
        var keptCount = 0
        var chosen = emptyList<Int>()
        // OVERLAP runs before OVERLAP_STRICT so the (cached) matching time is booked to the first strategy that needs it.
        for (arm in Arm.entries) {
            val pairsBefore = pairMs.size
            val t0 = System.nanoTime()
            val onCompare = { i: Int, ov: Overlap ->
                if (arm == Arm.OVERLAP) { frames[i].overlapToAnchor = ov.value; frames[i].reliable = ov.reliable; frames[i].msMatch = lastMs }
            }
            val r = ArmSelector.select(arm, sharp, tsArr, cap, pair, onCompare)
            val ms = (System.nanoTime() - t0) / 1e6
            r.chosen.forEach { frames[it].inArm[arm.ordinal] = true }
            if (arm == Arm.OVERLAP) {
                r.kept!!.forEach { frames[it].kept = true }
                r.groups!!.forEachIndexed { gi, g -> g.forEach { frames[it].groupId = gi } }
                groupCount = r.groups.size; keptCount = r.kept.size
            }
            if (arm == saveArm) chosen = r.chosen
            armStats.put(
                arm.label,
                JSONObject().put("chosen", JSONArray(r.chosen)).put("count", r.chosen.size)
                    .put("ms_select", ms.r2()).put("new_pair_matches", pairMs.size - pairsBefore)
                    .put("kept", r.kept?.size ?: JSONObject.NULL).put("groups", r.groups?.size ?: JSONObject.NULL),
            )
        }
        chosen.forEach { frames[it].chosen = true }
        var liveJson: JSONObject? = null
        if (liveMode == LiveMode.WITH_OFFLINE) {
            val tfin = System.nanoTime()
            val liveChosen = live!!.finish()
            liveFinishMs = (System.nanoTime() - tfin) / 1e6
            val offlineChosen = armStats.getJSONObject(Arm.OVERLAP.label).getJSONArray("chosen").let { a -> List(a.length()) { a.getInt(it) } }
            liveJson = liveSummary(liveChosen, offlineChosen, frames.map { it.kept })
            saveChosenJpegs(liveChosen, "LIVE")
        }

        writeCsv()
        saveChosenJpegs(chosen, saveArm.name)
        writeSummary(groupCount, keptCount, chosen, pairMs, pairCache.values.count { !it.reliable }, liveJson)
        frames.forEach { it.feat.release() }
        spoolDir.deleteRecursively()
        Log.i(TAG, "RUN_DONE ${runDir.absolutePath}")
        onDone(runDir)
    }

    private fun orbShape(): Pair<Int, Int> {
        val scale = OverlapEstimator.ORB_SIDE.toDouble() / maxOf(width, height)
        return Pair(Math.round(width * scale).toInt(), Math.round(height * scale).toInt())
    }

    private fun joinMetadata() {
        for (f in frames) {
            f.meta = metas[f.ts] ?: metas.keys.minByOrNull { Math.abs(it - f.ts) }
                ?.takeIf { Math.abs(it - f.ts) <= 1_000_000L }?.let { metas[it] }
        }
    }

    private fun writeCsv() {
        val sb = StringBuilder(
            "timestamp,sharpness,brightness,exposure_ns,iso,frame_duration_ns,focus_distance,lens_state,af_state,ae_state," +
                "ms_sharpness,ms_orb,ms_total,group_id,kept,chosen,ms_spool,ms_match,overlap_to_anchor,reliable," +
                Arm.entries.joinToString(",") { "arm_" + it.name } + "\n",
        )
        for (f in frames) {
            val m = f.meta
            sb.append(f.ts).append(',').append(f.sharp.f(3)).append(',').append(f.bright.f(2)).append(',')
                .append(m?.exposureNs ?: "").append(',').append(m?.iso ?: "").append(',').append(m?.frameDurationNs ?: "").append(',')
                .append(m?.focusDistance ?: "").append(',').append(m?.lensState ?: "").append(',').append(m?.afState ?: "").append(',')
                .append(m?.aeState ?: "").append(',').append(f.msSharp.f(2)).append(',').append(f.msOrb.f(2)).append(',')
                .append((f.msSharp + f.msOrb + f.msSpool).f(2)).append(',').append(f.groupId).append(',').append(if (f.kept) 1 else 0)
                .append(',').append(if (f.chosen) 1 else 0).append(',').append(f.msSpool.f(2)).append(',')
                .append(f.msMatch?.f(2) ?: "").append(',').append(f.overlapToAnchor?.toDouble()?.f(3) ?: "").append(',')
                .append(f.reliable?.let { if (it) 1 else 0 } ?: "")
            for (a in Arm.entries) sb.append(',').append(if (f.inArm[a.ordinal]) 1 else 0)
            sb.append('\n')
        }
        File(runDir, "run_frames.tmp").writeText(sb.toString())
        File(runDir, "run_frames.tmp").renameTo(File(runDir, "frames.csv"))
    }

    private fun saveChosenJpegs(chosen: List<Int>, label: String) {
        chosen.forEachIndexed { n, idx ->
            val f = frames[idx]
            val nv21 = File(spoolDir, "$idx.nv21").readBytes()
            val out = File(runDir, "chosen_${label}_%02d.jpg".format(n))
            out.outputStream().use { YuvImageCompat.toJpeg(nv21, f.spoolW, f.spoolH, 85, it) }
            val orientation = when (f.rotation) {
                90 -> ExifInterface.ORIENTATION_ROTATE_90
                180 -> ExifInterface.ORIENTATION_ROTATE_180
                270 -> ExifInterface.ORIENTATION_ROTATE_270
                else -> ExifInterface.ORIENTATION_NORMAL
            }
            ExifInterface(out.absolutePath).apply { setAttribute(ExifInterface.TAG_ORIENTATION, orientation.toString()); saveAttributes() }
        }
    }

    private fun writeSummary(groupCount: Int, keptCount: Int, chosen: List<Int>, pairMs: List<Double>, unreliablePairs: Int, liveJson: JSONObject? = null) {
        val ts = frames.map { it.ts }
        val spanS = (ts.last() - ts.first()) / 1e9
        val dts = ts.zipWithNext { a, b -> (b - a).toDouble() }
        val medDt = Selector.median(dts.toDoubleArray())
        val gapDropped = dts.sumOf { if (it > 1.5 * medDt) Math.round(it / medDt).toInt() - 1 else 0 }
        val presence = JSONObject()
        fun key(name: String, get: (Meta) -> Any?) {
            presence.put(name, JSONObject().put("present", frames.count { f -> f.meta?.let(get) != null }).put("total", frames.size))
        }
        key("SENSOR_EXPOSURE_TIME") { it.exposureNs }; key("SENSOR_SENSITIVITY") { it.iso }
        key("SENSOR_FRAME_DURATION") { it.frameDurationNs }; key("LENS_FOCUS_DISTANCE") { it.focusDistance }
        key("LENS_STATE") { it.lensState }; key("CONTROL_AF_STATE") { it.afState }; key("CONTROL_AE_STATE") { it.aeState }
        fun stats(vals: List<Double>) = JSONObject().apply {
            val s = vals.sorted().toDoubleArray()
            put("n", s.size)
            if (s.isNotEmpty()) {
                put("p50", Metrics.percentile(s, 50.0).r2()); put("p95", Metrics.percentile(s, 95.0).r2()); put("max", s.last().r2())
            }
        }
        val summary = JSONObject()
            .put("analysis_resolution_requested", resLabel)
            .put("analysis_resolution_actual", "${width}x$height")
            .put("requested_seconds", requestedSeconds)
            .put("frames_analyzed", frames.size)
            .put("span_s", spanS.r2())
            .put("achieved_fps", if (spanS > 0) ((frames.size - 1) / spanS).r2() else JSONObject.NULL)
            .put("capture_results_in_window", resultCount.get())
            .put("dropped_estimate_by_capture_results", resultCount.get() - frames.size)
            .put("dropped_estimate_by_timestamp_gaps", gapDropped)
            .put("median_frame_interval_ms", (medDt / 1e6).r2())
            .put("metadata_joined", frames.count { it.meta != null })
            .put("metadata_presence", presence)
            .put("ms_sharpness", stats(frames.map { it.msSharp }))
            .put("ms_orb_extract", stats(frames.map { it.msOrb }))
            .put("ms_spool_nv21", stats(frames.map { it.msSpool }))
            .put("ms_total_analyzer", stats(frames.map { it.msSharp + it.msOrb + it.msSpool }))
            .put("ms_match_homography_per_pair", stats(pairMs))
            .put("pairs_matched", pairMs.size)
            .put("pairs_unreliable", unreliablePairs)
            .put("gate_ratio", Selector.GATE_RATIO)
            .put("median_sharpness", Selector.median(DoubleArray(frames.size) { frames[it].sharp }).r2())
            .put("kept", keptCount)
            .put("groups", groupCount)
            .put("chosen", chosen.size)
            .put("selected_arm", saveArm.label)
            .put("cap", cap)
            .put("strategies", armStats)
            .put("chosen_frame_indices", JSONArray(chosen))
            .put("opencv_version", Core.VERSION)
            .put("thermal_status_start", thermalStart).put("thermal_status_end", thermal())
            .put("battery_temp_c_start", batteryStart.orNull()).put("battery_temp_c_end", batteryTempC().orNull())
            .put("device", "${android.os.Build.MODEL} API ${android.os.Build.VERSION.SDK_INT}")
        if (liveJson != null) summary.put("live", liveJson)
        summary.put("memory", memoryJson())
        File(runDir, "summary.json").writeText(summary.toString(2))
    }

    private fun memoryJson(): JSONObject {
        val mi = android.os.Debug.MemoryInfo(); android.os.Debug.getMemoryInfo(mi)
        val nat = memSamples.map { it[1] }; val jav = memSamples.map { it[2] }
        return JSONObject().put("samples", memSamples.size)
            .put("native_heap_mb_first", nat.firstOrNull()?.r2() ?: JSONObject.NULL).put("native_heap_mb_max", nat.maxOrNull()?.r2() ?: JSONObject.NULL)
            .put("java_heap_mb_first", jav.firstOrNull()?.r2() ?: JSONObject.NULL).put("java_heap_mb_max", jav.maxOrNull()?.r2() ?: JSONObject.NULL)
            .put("pss_total_mb_at_end", (mi.totalPss / 1024.0).r2())
            .put("series_t_s_native_java_mb", JSONArray(memSamples.map { JSONArray(it.toList()) }))
    }

    /** Summary + replay trace of the streaming selector; [offlineOverlap] and [offlineKept] are set only when the offline strategies ran too. */
    private fun liveSummary(liveChosen: List<Int>, offlineOverlap: List<Int>?, offlineKept: List<Boolean>?): JSONObject {
        val l = live!!
        val gate = l.gateLog
        val disagree = if (offlineKept != null) gate.indices.count { gate[it] != offlineKept[it] } else null
        fun stats(v: List<Double>) = JSONObject().apply {
            val s = v.sorted().toDoubleArray(); put("n", s.size)
            if (s.isNotEmpty()) { put("p50", Metrics.percentile(s, 50.0).r2()); put("p95", Metrics.percentile(s, 95.0).r2()); put("max", s.last().r2()) }
        }
        val trace = JSONObject().put("params", JSONObject().put("cap", cap).put("ratio", Selector.GATE_RATIO).put("max_gap_ns", ArmSelector.MAX_GAP_NS).put("max_reps", LiveSelector.DEFAULT_MAX_REPS))
            .put("frames", JSONArray(liveRows.map { JSONArray(listOf(it[0].toInt(), it[1].toLong(), it[2], it[3].toInt())) }))
            .put("pairs", JSONArray(livePairLog.map { JSONArray(listOf(it[0].toInt(), it[1].toInt(), it[2], it[3].toInt())) }))
            .put("chosen", JSONArray(liveChosen))
        File(runDir, "live_trace.json").writeText(trace.toString())
        return JSONObject().put("mode", liveMode.name).put("chosen", JSONArray(liveChosen)).put("count", liveChosen.size)
            .put("frames_pushed", l.pushed).put("gate_rejected", l.gateRejected).put("groups_closed", l.groupsClosed).put("merges", l.merges)
            .put("max_frames_held_at_once", l.maxRetained).put("ms_finish_after_last_frame", liveFinishMs.r2())
            .put("auto_stopped_at_groups", if (autoStopped) autoStopGroups else JSONObject.NULL)
            .put("offline_overlap_chosen", offlineOverlap?.let { JSONArray(it) } ?: JSONObject.NULL)
            .put("equals_offline_overlap", offlineOverlap?.let { it == liveChosen } ?: JSONObject.NULL)
            .put("shared_with_offline_overlap", offlineOverlap?.let { o -> liveChosen.count { it in o } } ?: JSONObject.NULL)
            .put("gate_decisions_differing_from_offline", disagree ?: JSONObject.NULL)
            .put("ms_push_per_frame", stats(livePushMs))
            .put("ms_pair_match", stats(livePairLog.map { it[4] })).put("pairs_matched", livePairLog.size)
            .put("ms_spool_when_held", stats(liveRows.filter { it[7] > 0 }.map { it[7] }))
    }

    /** ONLY mode: the streaming selector's result, written without any per-frame list of features. */
    private fun finishLiveOnly() {
        val l = live!!
        if (liveRows.isEmpty()) {
            File(runDir, "summary.json").writeText("""{"error":"no frames analyzed"}""")
            onDone(runDir); return
        }
        val tfin = System.nanoTime()
        val liveChosen = l.finish()
        liveFinishMs = (System.nanoTime() - tfin) / 1e6
        val liveJson = liveSummary(liveChosen, null, null)
        liveChosen.forEachIndexed { n, idx ->
            val d = liveSpoolDims.getValue(idx)
            val out = File(runDir, "chosen_LIVE_%02d.jpg".format(n))
            out.outputStream().use { YuvImageCompat.toJpeg(File(spoolDir, "$idx.nv21").readBytes(), d[0], d[1], 85, it) }
            val orientation = when (d[2]) {
                90 -> ExifInterface.ORIENTATION_ROTATE_90; 180 -> ExifInterface.ORIENTATION_ROTATE_180
                270 -> ExifInterface.ORIENTATION_ROTATE_270; else -> ExifInterface.ORIENTATION_NORMAL
            }
            ExifInterface(out.absolutePath).apply { setAttribute(ExifInterface.TAG_ORIENTATION, orientation.toString()); saveAttributes() }
        }
        val ts = liveRows.map { it[1].toLong() }
        val spanS = (ts.last() - ts.first()) / 1e9
        val dts = ts.zipWithNext { a, b -> (b - a).toDouble() }
        val summary = JSONObject().put("mode", "live_only")
            .put("analysis_resolution_actual", "${width}x$height").put("requested_seconds", requestedSeconds)
            .put("frames_analyzed", liveRows.size).put("span_s", spanS.r2())
            .put("achieved_fps", if (spanS > 0) ((liveRows.size - 1) / spanS).r2() else JSONObject.NULL)
            .put("median_frame_interval_ms", (Selector.median(dts.toDoubleArray()) / 1e6).r2())
            .put("capture_results_in_window", resultCount.get())
            .put("dropped_estimate_by_capture_results", resultCount.get() - liveRows.size)
            .put("ms_sharpness", JSONObject().put("p50", Metrics.percentile(liveRows.map { it[4] }.sorted().toDoubleArray(), 50.0).r2()).put("p95", Metrics.percentile(liveRows.map { it[4] }.sorted().toDoubleArray(), 95.0).r2()))
            .put("ms_orb_extract", JSONObject().put("p50", Metrics.percentile(liveRows.map { it[5] }.sorted().toDoubleArray(), 50.0).r2()).put("p95", Metrics.percentile(liveRows.map { it[5] }.sorted().toDoubleArray(), 95.0).r2()))
            .put("ms_analyzer_total", JSONObject().put("p50", Metrics.percentile(liveRows.map { it[4] + it[5] + it[6] + it[7] }.sorted().toDoubleArray(), 50.0).r2()).put("p95", Metrics.percentile(liveRows.map { it[4] + it[5] + it[6] + it[7] }.sorted().toDoubleArray(), 95.0).r2()).put("max", liveRows.maxOf { it[4] + it[5] + it[6] + it[7] }.r2()))
            .put("live", liveJson).put("memory", memoryJson())
            .put("opencv_version", Core.VERSION)
            .put("thermal_status_start", thermalStart).put("thermal_status_end", thermal())
            .put("battery_temp_c_start", batteryStart.orNull()).put("battery_temp_c_end", batteryTempC().orNull())
            .put("device", "${android.os.Build.MODEL} API ${android.os.Build.VERSION.SDK_INT}")
        File(runDir, "summary.json").writeText(summary.toString(2))
        liveFeats.values.forEach { it.release() }; liveFeats.clear()
        spoolDir.deleteRecursively()
        Log.i(TAG, "RUN_DONE ${runDir.absolutePath}")
        onDone(runDir)
    }

    private fun thermal(): Int = (ctx.getSystemService(Context.POWER_SERVICE) as PowerManager).currentThermalStatus

    private fun batteryTempC(): Double {
        val i: Intent? = ctx.registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        return (i?.getIntExtra(BatteryManager.EXTRA_TEMPERATURE, Int.MIN_VALUE) ?: Int.MIN_VALUE).let { if (it == Int.MIN_VALUE) Double.NaN else it / 10.0 }
    }

    private fun Double.orNull(): Any = if (isNaN()) JSONObject.NULL else this
    private fun Double.f(d: Int) = "%.${d}f".format(Locale.US, this)
    private fun Double.r2() = Math.round(this * 100) / 100.0

    companion object {
        const val TAG = "MLCDemo"
    }
}

object YuvImageCompat {
    fun toJpeg(nv21: ByteArray, w: Int, h: Int, quality: Int, out: java.io.OutputStream) {
        android.graphics.YuvImage(nv21, ImageFormat.NV21, w, h, null).compressToJpeg(Rect(0, 0, w, h), quality, out)
    }
}
