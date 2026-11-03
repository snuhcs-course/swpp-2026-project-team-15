// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
package com.mylittlechef.researchdemo

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import org.opencv.core.Core
import org.opencv.core.CvType
import org.opencv.core.Mat
import org.opencv.core.Point
import org.opencv.core.Rect
import org.opencv.core.Scalar
import org.opencv.core.Size
import org.opencv.imgproc.Imgproc
import java.io.File
import java.util.Random

/**
 * Camera-free check of the OpenCV path on a synthetic textured sweep whose true overlap is known
 * (window of width [W] sliding [STEP] px per frame), plus ORB / homography timing on this phone.
 * Needed because a dark or featureless camera view makes every estimate unreliable (nothing to time).
 */
class Benchmark(private val ctx: Context) {
    fun run(): File {
        val out = JSONObject().put("note", "synthetic textured sweep, not camera frames; truth overlap = 1 - STEP*|b-a|/W")
        val shapes = JSONArray()
        for ((w, h) in listOf(512 to 384, 512 to 288)) shapes.put(runShape(w, h))
        out.put("shapes", shapes).put("opencv_version", Core.VERSION)
        val f = File(ctx.getExternalFilesDir(null), "bench.json")
        f.writeText(out.toString(2))
        return f
    }

    private fun texture(w: Int, h: Int): Mat {
        val rnd = Random(20261102)
        val m = Mat(h, w, CvType.CV_8UC1)
        Core.randn(m, 128.0, 40.0)
        Imgproc.GaussianBlur(m, m, Size(5.0, 5.0), 1.5)
        repeat(400) {
            val c = Scalar(rnd.nextInt(256).toDouble())
            val p = Point(rnd.nextInt(w).toDouble(), rnd.nextInt(h).toDouble())
            when (rnd.nextInt(3)) {
                0 -> Imgproc.circle(m, p, 3 + rnd.nextInt(25), c, if (rnd.nextBoolean()) -1 else 2)
                1 -> Imgproc.rectangle(m, p, Point(p.x + 5 + rnd.nextInt(60), p.y + 5 + rnd.nextInt(60)), c, if (rnd.nextBoolean()) -1 else 2)
                else -> Imgproc.putText(m, "MLC${rnd.nextInt(99)}", p, Imgproc.FONT_HERSHEY_SIMPLEX, 0.5 + rnd.nextDouble(), c, 2)
            }
        }
        return m
    }

    private fun runShape(w: Int, h: Int): JSONObject {
        val frames = 60
        val big = texture(w + STEP * frames, h)
        val est = OverlapEstimator()
        val feats = ArrayList<Features>()
        val extractMs = ArrayList<Double>()
        repeat(3 + frames) { i ->
            val k = maxOf(0, i - 3) // first three iterations warm up the JIT and ORB, frame 0 is repeated
            val win = big.submat(Rect(k * STEP, 0, w, h))
            val data = ByteArray(w * h).also { win.get(0, 0, it) }
            val t = System.nanoTime()
            val f = est.extract(Gray(w, h, data))
            val ms = (System.nanoTime() - t) / 1e6
            if (i >= 3) { feats.add(f); extractMs.add(ms) } else f.release()
        }
        val pairMs = ArrayList<Double>()
        val rows = JSONArray()
        var absErr = 0.0; var n = 0; var unreliableWhereTruthHigh = 0; var truthHigh = 0
        repeat(3) { est.overlap(feats[0], feats[1], w, h) } // warm up
        for (i in 1 until frames) {
            val t = System.nanoTime()
            val ov = est.overlap(feats[0], feats[i], w, h)
            pairMs.add((System.nanoTime() - t) / 1e6)
            val truth = maxOf(0.0, 1.0 - STEP.toDouble() * i / w)
            if (truth >= 0.3) {
                truthHigh++
                if (!ov.reliable) unreliableWhereTruthHigh++ else { absErr += Math.abs(ov.value - truth); n++ }
            }
            rows.put(JSONObject().put("i", i).put("truth", Math.round(truth * 1000) / 1000.0).put("estimate", ov.value.toDouble()).put("reliable", ov.reliable))
        }
        val pair = { a: Int, b: Int -> est.overlap(feats[a], feats[b], w, h) }
        val groups = Selector.group((0 until frames).toList(), pair)
        val reps = groups.map { it.first() }
        val chosen = Selector.farthestFirst(reps, 2, pair)
        fun stat(v: List<Double>) = v.sorted().toDoubleArray().let {
            JSONObject().put("n", it.size).put("p50", Metrics.percentile(it, 50.0)).put("p95", Metrics.percentile(it, 95.0)).put("max", it.last())
        }
        feats.forEach { it.release() }
        return JSONObject().put("frame", "${w}x$h").put("step_px", STEP).put("frames", frames)
            .put("keypoints_frame0", feats[0].count)
            .put("ms_orb_extract", stat(extractMs)).put("ms_match_homography_per_pair", stat(pairMs))
            .put("pairs_with_truth_ge_0.3", truthHigh).put("of_which_unreliable", unreliableWhereTruthHigh)
            .put("mean_abs_error_reliable_pairs", if (n > 0) absErr / n else JSONObject.NULL)
            .put("groups_found", groups.size).put("group_first_frames", JSONArray(groups.map { it.first() }))
            .put("groups_expected", "new group when 1 - 12*i/512 < 0.5, i.e. every 22 frames: starts at 0, 22, 44")
            .put("farthest_first_of_groups_k2", JSONArray(chosen))
            .put("pairs", rows)
    }

    companion object {
        const val STEP = 12
    }
}
