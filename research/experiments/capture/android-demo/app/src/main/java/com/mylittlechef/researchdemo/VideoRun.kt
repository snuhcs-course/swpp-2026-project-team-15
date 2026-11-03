// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
package com.mylittlechef.researchdemo

import android.content.Context
import android.graphics.Bitmap
import android.media.MediaExtractor
import android.media.MediaFormat
import android.media.MediaMetadataRetriever
import android.os.Build
import android.os.PowerManager
import org.json.JSONArray
import org.json.JSONObject
import org.opencv.core.Core
import java.io.File

/**
 * Video-file input for the same analysis the live camera runs (no camera needed): every native frame of a clip is decoded
 * with MediaMetadataRetriever.getFrameAtIndex, analysed exactly like a camera frame (Y plane -> 256 px sharpness, 512 px
 * ORB), then all six strategies are computed by the same ArmSelector. Per-stage on-device times are written to
 * getExternalFilesDir/video-runs/<clip>.json (app-private; removed with the app).
 *
 * The bitmap path converts ARGB to luma with the BT.601 weights the camera YUV uses, so the Y values differ slightly from
 * the original video's decoder output; parity with the host decode is measured, not assumed (see the README).
 */
class VideoRun(private val ctx: Context) {
    private val estimator = OverlapEstimator()

    private class Frame(val ts: Long, val sharp: Double, val feat: Features, val msDecode: Double, val msGray: Double,
                        val msSharp: Double, val msOrb: Double)

    fun run(path: String, cap: Int, decoder: String = "retriever", livePass: Boolean = false, maxReps: Int = LiveSelector.DEFAULT_MAX_REPS, step: Int = 1): File {
        val codec = decoder == "codec"
        val name = File(path).nameWithoutExtension
        val outDir = File(ctx.getExternalFilesDir(null), "video-runs").apply { mkdirs() }
        val mmr = MediaMetadataRetriever()
        mmr.setDataSource(path)
        val count = mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_FRAME_COUNT)!!.toInt()
        val w = mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)!!.toInt()
        val h = mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)!!.toInt()
        val rotation = mmr.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_ROTATION)?.toInt() ?: 0
        val sampleTimes = sampleTimesNs(path)
        val thermalStart = thermal()

        val frames = ArrayList<Frame>(count)
        val t0 = System.nanoTime()
        if (codec) {
            var first = -1L
            CodecDecoder.forEachFrame(path) { i, tsNs, y, rs, fw, fh ->
                if (first < 0) first = tsNs
                val tg = System.nanoTime()
                val small = Metrics.downscale(y, rs, fw, fh, 256)
                val big = Metrics.downscale(y, rs, fw, fh, OverlapEstimator.ORB_SIDE)
                val msGray = (System.nanoTime() - tg) / 1e6
                val ts0 = System.nanoTime()
                val sharp = Metrics.laplacianVariance(small)
                val msSharp = (System.nanoTime() - ts0) / 1e6
                val to = System.nanoTime()
                val feat = estimator.extract(big)
                frames.add(Frame(tsNs - first, sharp, feat, 0.0, msGray, msSharp, (System.nanoTime() - to) / 1e6))
            }
        } else for (i in 0 until count) {
            val td = System.nanoTime()
            val bmp: Bitmap = mmr.getFrameAtIndex(i) ?: break
            val msDecode = (System.nanoTime() - td) / 1e6
            val tg = System.nanoTime()
            val y = lumaPlane(bmp)
            val bw = bmp.width; val bh = bmp.height
            bmp.recycle()
            val small = Metrics.downscale(y, bw, bw, bh, 256)
            val big = Metrics.downscale(y, bw, bw, bh, OverlapEstimator.ORB_SIDE)
            val msGray = (System.nanoTime() - tg) / 1e6
            val ts0 = System.nanoTime()
            val sharp = Metrics.laplacianVariance(small)
            val msSharp = (System.nanoTime() - ts0) / 1e6
            val to = System.nanoTime()
            val feat = estimator.extract(big)
            val msOrb = (System.nanoTime() - to) / 1e6
            val ts = if (i < sampleTimes.size) sampleTimes[i] else Math.round(i * 1e9 / 30.0)
            frames.add(Frame(ts - (sampleTimes.firstOrNull() ?: 0L), sharp, feat, msDecode, msGray, msSharp, msOrb))
        }
        mmr.release()
        val msAnalysisTotal = (System.nanoTime() - t0) / 1e6

        val ow: Int; val oh: Int
        run {
            val sc = OverlapEstimator.ORB_SIDE.toDouble() / maxOf(w, h)
            ow = Math.round(w * sc).toInt(); oh = Math.round(h * sc).toInt()
        }
        val pairCache = HashMap<Long, Overlap>()
        val pairMs = ArrayList<Double>()
        val pairLog = JSONArray()
        val pair = { a: Int, b: Int ->
            pairCache.getOrPut(a.toLong() * 1_000_000 + b) {
                val t = System.nanoTime()
                val o = estimator.overlap(frames[a].feat, frames[b].feat, ow, oh)
                pairMs.add((System.nanoTime() - t) / 1e6)
                pairLog.put(JSONArray().put(a).put(b).put(o.value.toDouble()).put(o.reliable))
                o
            }
        }
        val sharp = DoubleArray(frames.size) { frames[it].sharp }
        val tsArr = LongArray(frames.size) { frames[it].ts }
        val arms = JSONObject()
        val gateStats = JSONObject()
        for (arm in Arm.entries) { // OVERLAP first so its pair matches are booked to it, as in the live run
            val before = pairMs.size
            val ts1 = System.nanoTime()
            val r = ArmSelector.select(arm, sharp, tsArr, cap, pair)
            val ms = (System.nanoTime() - ts1) / 1e6
            arms.put(arm.label, JSONObject().put("chosen", JSONArray(r.chosen)).put("count", r.chosen.size)
                .put("ms_select", r2(ms)).put("new_pair_matches", pairMs.size - before)
                .put("kept", r.kept?.size ?: JSONObject.NULL).put("groups", r.groups?.size ?: JSONObject.NULL)
                .put("group_sizes", r.groups?.let { g -> JSONArray(g.map { it.size }) } ?: JSONObject.NULL))
            if (arm == Arm.OVERLAP) gateStats.put("overlap_groups", r.groups?.size ?: 0)
        }
        val unreliable = pairCache.values.count { !it.reliable }
        val perFrameMs = frames.map { it.msGray + it.msSharp + it.msOrb } // analysis without decode (the camera path has no decode)
        val liveJson = if (livePass) livePass(path, cap, ow, oh, arms.getJSONObject(Arm.OVERLAP.label).getJSONArray("chosen"), maxReps, step) else null
        val out = JSONObject()
            .put("decoder", decoder)
            .put("clip", name).put("frames", frames.size).put("declared_frames", count)
            .put("width", w).put("height", h).put("rotation_metadata", rotation).put("cap", cap)
            .put("sample_times_ns_first_last", JSONArray(listOf(sampleTimes.firstOrNull() ?: -1L, sampleTimes.lastOrNull() ?: -1L)))
            .put("ms_analysis_total_with_decode", r2(msAnalysisTotal))
            .put("ms_decode_per_frame", if (codec) JSONObject.NULL else stats(frames.map { it.msDecode }))
            .put("ms_gray_and_resize_per_frame", stats(frames.map { it.msGray }))
            .put("ms_sharpness_per_frame", stats(frames.map { it.msSharp }))
            .put("ms_orb_extract_per_frame", stats(frames.map { it.msOrb }))
            .put("ms_analysis_per_frame_without_decode", stats(perFrameMs))
            .put("ms_match_homography_per_pair", stats(pairMs))
            .put("pairs_matched", pairMs.size).put("pairs_unreliable", unreliable)
            .put("keypoints_per_frame", stats(frames.map { it.feat.count.toDouble() }))
            .put("median_sharpness", r2(Selector.median(sharp)))
            .put("strategies", arms)
            .put("per_frame", JSONArray().also { a ->
                frames.forEachIndexed { i, f -> a.put(JSONArray().put(i).put(f.ts).put(f.sharp).put(f.feat.count)) }
            })
            .put("pairs", pairLog) // [a, b, overlap, reliable] for every pair the strategies asked for, to replay on the host
            .put("live_pass", liveJson ?: JSONObject.NULL)
            .put("opencv_version", Core.VERSION)
            .put("thermal_status_start", thermalStart).put("thermal_status_end", thermal())
            .put("device", "${Build.MODEL} API ${Build.VERSION.SDK_INT}")
        frames.forEach { it.feat.release() }
        val f = File(outDir, if (codec) "$name.codec.json" else "$name.json")
        f.writeText(out.toString())
        return f
    }

    /**
     * Streaming pass: decode again and push each frame to LiveSelector as it arrives, keeping features only for the frames
     * the selector still holds (so memory does not grow with the clip). Compared with the offline OVERLAP choice on the same frames.
     */
    private fun livePass(path: String, cap: Int, ow: Int, oh: Int, offlineOverlap: JSONArray, maxReps: Int, step: Int): JSONObject {
        val feats = HashMap<Int, Features>()
        val cache = HashMap<Long, Overlap>()
        val pairLog = JSONArray(); val pairMs = ArrayList<Double>()
        val rows = JSONArray(); val pushMs = ArrayList<Double>()
        val nat = ArrayList<Double>(); val jav = ArrayList<Double>()
        val sel = LiveSelector(cap, maxReps = maxReps, pair = { a, b ->
            cache.getOrPut(a.toLong() * 1_000_000 + b) {
                val t = System.nanoTime()
                val o = estimator.overlap(feats.getValue(a), feats.getValue(b), ow, oh)
                pairMs.add((System.nanoTime() - t) / 1e6)
                pairLog.put(JSONArray().put(a).put(b).put(o.value.toDouble()).put(o.reliable))
                o
            }
        }, release = { feats.remove(it)?.release() })
        var first = -1L
        System.gc()
        val rt = Runtime.getRuntime()
        val nat0 = android.os.Debug.getNativeHeapAllocatedSize() / 1048576.0
        val t0 = System.nanoTime()
        val n = CodecDecoder.forEachFrame(path) { i, tsNs, y, rs, fw, fh ->
            if (first < 0) first = tsNs
            if (i % step != 0) return@forEachFrame // analyse every step-th frame only (step 2 = 15 fps analysis of a 30 fps clip)
            val small = Metrics.downscale(y, rs, fw, fh, 256)
            val sharp = Metrics.laplacianVariance(small)
            feats[i] = estimator.extract(Metrics.downscale(y, rs, fw, fh, OverlapEstimator.ORB_SIDE))
            val tp = System.nanoTime()
            val pass = sel.push(i, tsNs - first, sharp)
            pushMs.add((System.nanoTime() - tp) / 1e6)
            rows.put(JSONArray().put(i).put(tsNs - first).put(sharp).put(if (pass) 1 else 0))
            if (i % 10 == 0) { nat.add(android.os.Debug.getNativeHeapAllocatedSize() / 1048576.0); jav.add((rt.totalMemory() - rt.freeMemory()) / 1048576.0) }
        }
        val streamWall = (System.nanoTime() - t0) / 1e6
        val pairsDuringStream = pairLog.length()
        val tf = System.nanoTime()
        val chosen = sel.finish()
        val msFinish = (System.nanoTime() - tf) / 1e6
        val wall = (System.nanoTime() - t0) / 1e6
        val off = List(offlineOverlap.length()) { offlineOverlap.getInt(it) }
        feats.values.forEach { it.release() }
        return JSONObject().put("frames", n).put("chosen", JSONArray(chosen)).put("count", chosen.size)
            .put("offline_overlap_same_decoder", offlineOverlap).put("equals_offline_overlap", off == chosen)
            .put("shared_with_offline_overlap", chosen.count { it in off })
            .put("gate_rejected", sel.gateRejected).put("groups_closed", sel.groupsClosed).put("merges", sel.merges)
            .put("max_frames_held_at_once", sel.maxRetained)
            .put("native_heap_mb_start", r2(nat0)).put("native_heap_mb_max_during", r2(nat.maxOrNull() ?: 0.0))
            .put("java_heap_mb_max_during", r2(jav.maxOrNull() ?: 0.0))
            .put("max_reps", maxReps).put("analysis_every_nth_frame", step)
            .put("wall_ms_decode_and_live", r2(wall)).put("ms_stream_part", r2(streamWall)).put("ms_finish_after_last_frame", r2(msFinish))
            .put("pairs_during_stream", pairsDuringStream).put("pairs_in_finish", pairLog.length() - pairsDuringStream)
            .put("ms_push_per_frame", stats(pushMs)).put("ms_pair_match", if (pairMs.isEmpty()) JSONObject.NULL else stats(pairMs))
            .put("pairs_matched", pairMs.size)
            .put("trace_frames", rows).put("trace_pairs", pairLog)
    }

    /** Presentation time (ns) of every sample of the first video track, in decode order sorted by time. */
    private fun sampleTimesNs(path: String): LongArray {
        val ex = MediaExtractor()
        try {
            ex.setDataSource(path)
            val track = (0 until ex.trackCount).first { ex.getTrackFormat(it).getString(MediaFormat.KEY_MIME)!!.startsWith("video/") }
            ex.selectTrack(track)
            val times = ArrayList<Long>()
            while (ex.sampleTime >= 0) {
                times.add(ex.sampleTime * 1000L)
                if (!ex.advance()) break
            }
            return times.sorted().toLongArray()
        } finally {
            ex.release()
        }
    }

    /** ARGB bitmap -> row-major luma (BT.601, rounded), stride = width. */
    private fun lumaPlane(bmp: Bitmap): ByteArray {
        val w = bmp.width; val h = bmp.height
        val px = IntArray(w * h)
        bmp.getPixels(px, 0, w, 0, 0, w, h)
        val y = ByteArray(w * h)
        for (i in px.indices) {
            val p = px[i]
            val r = (p shr 16) and 0xFF; val g = (p shr 8) and 0xFF; val b = p and 0xFF
            y[i] = ((77 * r + 150 * g + 29 * b + 128) shr 8).toByte()
        }
        return y
    }

    private fun thermal(): Int = (ctx.getSystemService(Context.POWER_SERVICE) as PowerManager).currentThermalStatus

    private fun r2(v: Double) = Math.round(v * 100) / 100.0

    private fun stats(v: List<Double>): JSONObject {
        val s = v.sorted().toDoubleArray()
        return JSONObject().put("n", s.size).put("p50", r2(Metrics.percentile(s, 50.0)))
            .put("p95", r2(Metrics.percentile(s, 95.0))).put("max", r2(s.last()))
    }
}
