// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-03; human review pending.
package com.mylittlechef.researchdemo

import org.opencv.calib3d.Calib3d
import org.opencv.core.Core
import org.opencv.core.CvType
import org.opencv.core.DMatch
import org.opencv.core.Mat
import org.opencv.core.MatOfDMatch
import org.opencv.core.MatOfKeyPoint
import org.opencv.core.MatOfPoint2f
import org.opencv.core.Point
import org.opencv.features2d.BFMatcher
import org.opencv.features2d.ORB
import org.opencv.imgproc.Imgproc

/** ORB keypoint coordinates (x, y interleaved) and descriptors of one frame. */
class Features(val pts: FloatArray, val desc: Mat?) {
    val count get() = pts.size / 2
    fun release() = desc?.release()
}

/** Port of sweep_select.py: ORB 500 on a 512 px gray copy, cross-checked BFMatcher, RANSAC homography (4 px). */
class OverlapEstimator {
    private val orb = ORB.create(500)
    private val matcher = BFMatcher.create(Core.NORM_HAMMING, true)

    fun extract(g: Gray): Features {
        val mat = Mat(g.h, g.w, CvType.CV_8UC1)
        mat.put(0, 0, g.data)
        val kp = MatOfKeyPoint()
        val desc = Mat()
        orb.detectAndCompute(mat, Mat(), kp, desc)
        mat.release()
        val arr = kp.toArray()
        kp.release()
        val pts = FloatArray(arr.size * 2)
        arr.forEachIndexed { i, k -> pts[2 * i] = k.pt.x.toFloat(); pts[2 * i + 1] = k.pt.y.toFloat() }
        return Features(pts, if (arr.isEmpty()) null else desc)
    }

    /** Share of frame [b], warped into frame [a], that lies inside frame [a]; [w] x [h] is the 512 px copy size. */
    fun overlap(a: Features, b: Features, w: Int, h: Int): Overlap {
        val unreliable = Overlap(0f, false)
        if (a.desc == null || b.desc == null || a.count < 8 || b.count < 8) return unreliable
        val matches = MatOfDMatch()
        matcher.match(a.desc, b.desc, matches)
        val list: List<DMatch> = matches.toList()
        matches.release()
        if (list.size < MIN_INLIERS) return unreliable
        val src = MatOfPoint2f(*list.map { Point(b.pts[2 * it.trainIdx].toDouble(), b.pts[2 * it.trainIdx + 1].toDouble()) }.toTypedArray())
        val dst = MatOfPoint2f(*list.map { Point(a.pts[2 * it.queryIdx].toDouble(), a.pts[2 * it.queryIdx + 1].toDouble()) }.toTypedArray())
        val mask = Mat()
        val hom = Calib3d.findHomography(src, dst, Calib3d.RANSAC, 4.0, mask)
        val inliers = if (hom.empty()) 0 else Core.countNonZero(mask)
        src.release(); dst.release(); mask.release()
        if (hom.empty() || inliers < MIN_INLIERS) {
            hom.release()
            return unreliable
        }
        val rect = MatOfPoint2f(Point(0.0, 0.0), Point(w.toDouble(), 0.0), Point(w.toDouble(), h.toDouble()), Point(0.0, h.toDouble()))
        val quad = Mat()
        Core.perspectiveTransform(rect, quad, hom)
        val quad32 = Mat()
        quad.convertTo(quad32, CvType.CV_32FC2)
        val inter = Mat()
        val area = Imgproc.intersectConvexConvex(rect, quad32, inter)
        rect.release(); quad.release(); quad32.release(); inter.release(); hom.release()
        return Overlap((area / (w.toDouble() * h)).toFloat().coerceIn(0f, 1f), true)
    }

    companion object {
        const val MIN_INLIERS = 12
        const val ORB_SIDE = 512
    }
}
