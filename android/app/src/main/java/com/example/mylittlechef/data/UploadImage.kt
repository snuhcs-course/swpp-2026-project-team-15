// AI-generated with Claude Code (Opus 5.5), 2026-10-14; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.ExifInterface
import java.io.ByteArrayInputStream
import java.io.File
import kotlin.math.roundToInt

// Gemini tokens do not depend on photo size, so the limit only trims upload time.
const val MAX_UPLOAD_SIDE = 2048
private const val JPEG_QUALITY = 90

// Orientation keeps the photo upright for recognition; GPS is dropped on purpose.
private val COPIED_EXIF_TAGS = listOf(
    ExifInterface.TAG_ORIENTATION,
    ExifInterface.TAG_DATETIME,
    ExifInterface.TAG_DATETIME_ORIGINAL,
    ExifInterface.TAG_MAKE,
    ExifInterface.TAG_MODEL
)

class UploadImage(val bytes: ByteArray, val mimeType: String)

/** Size within [maxSide] that keeps the aspect ratio; unchanged when already small enough. */
fun fitWithin(width: Int, height: Int, maxSide: Int): Pair<Int, Int> {
    val longest = maxOf(width, height)
    if (longest <= maxSide) return width to height
    val scale = maxSide.toDouble() / longest
    return (width * scale).roundToInt().coerceAtLeast(1) to (height * scale).roundToInt().coerceAtLeast(1)
}

/** Largest power-of-two decode step that still leaves at least the target size. */
fun sampleSizeFor(width: Int, height: Int, targetWidth: Int, targetHeight: Int): Int {
    var sample = 1
    while (width / (sample * 2) >= targetWidth && height / (sample * 2) >= targetHeight) {
        sample *= 2
    }
    return sample
}

/**
 * Returns the photo unchanged when it fits [MAX_UPLOAD_SIDE] or cannot be decoded;
 * otherwise a resized JPEG carrying the original orientation and capture metadata.
 */
fun prepareForUpload(original: ByteArray, mimeType: String?, workDir: File): UploadImage {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    BitmapFactory.decodeByteArray(original, 0, original.size, bounds)
    val type = mimeType ?: bounds.outMimeType ?: "image/jpeg"
    val (width, height) = fitWithin(bounds.outWidth, bounds.outHeight, MAX_UPLOAD_SIDE)
    if (bounds.outWidth <= 0 || (width == bounds.outWidth && height == bounds.outHeight)) {
        return UploadImage(original, type)
    }

    val options = BitmapFactory.Options().apply {
        inSampleSize = sampleSizeFor(bounds.outWidth, bounds.outHeight, width, height)
    }
    val sampled = BitmapFactory.decodeByteArray(original, 0, original.size, options)
        ?: return UploadImage(original, type)
    val resized = Bitmap.createScaledBitmap(sampled, width, height, true)

    // ExifInterface can only write metadata into a file.
    val file = File.createTempFile("upload", ".jpg", workDir)
    try {
        file.outputStream().use { resized.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, it) }
        copyExif(original, file)
        return UploadImage(file.readBytes(), "image/jpeg")
    } finally {
        file.delete()
    }
}

private fun copyExif(original: ByteArray, target: File) {
    val source = ExifInterface(ByteArrayInputStream(original))
    val copy = ExifInterface(target.path)
    COPIED_EXIF_TAGS.forEach { tag -> source.getAttribute(tag)?.let { copy.setAttribute(tag, it) } }
    copy.saveAttributes()
}
