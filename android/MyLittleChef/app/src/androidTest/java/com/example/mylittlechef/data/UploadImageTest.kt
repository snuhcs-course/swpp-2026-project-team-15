// AI-generated with Claude Code (Opus 5.5), 2026-10-14; review pending by Jaehyuk Choi.
package com.example.mylittlechef.data

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.media.ExifInterface
import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import java.io.ByteArrayInputStream
import java.io.File

@RunWith(AndroidJUnit4::class)
class UploadImageTest {
    private val cacheDir: File = InstrumentationRegistry.getInstrumentation().targetContext.cacheDir

    private fun photo(width: Int, height: Int): ByteArray {
        val file = File.createTempFile("photo", ".jpg", cacheDir)
        try {
            val bitmap = Bitmap.createBitmap(width, height, Bitmap.Config.ARGB_8888)
            file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.JPEG, 90, it) }
            ExifInterface(file.path).apply {
                setAttribute(ExifInterface.TAG_ORIENTATION, ExifInterface.ORIENTATION_ROTATE_90.toString())
                setAttribute(ExifInterface.TAG_DATETIME_ORIGINAL, "2026:10:14 12:00:00")
                setAttribute(ExifInterface.TAG_GPS_LATITUDE, "37/1,27/1,0/1")
                setAttribute(ExifInterface.TAG_GPS_LATITUDE_REF, "N")
                saveAttributes()
            }
            return file.readBytes()
        } finally {
            file.delete()
        }
    }

    @Test
    fun prepareForUpload_largePhoto_resizesAndKeepsOrientationWithoutGps() {
        val result = prepareForUpload(photo(4000, 3000), "image/jpeg", cacheDir)

        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(result.bytes, 0, result.bytes.size, bounds)
        val exif = ExifInterface(ByteArrayInputStream(result.bytes))
        assertEquals(2048 to 1536, bounds.outWidth to bounds.outHeight)
        assertEquals("image/jpeg", result.mimeType)
        assertEquals(ExifInterface.ORIENTATION_ROTATE_90.toString(), exif.getAttribute(ExifInterface.TAG_ORIENTATION))
        assertEquals("2026:10:14 12:00:00", exif.getAttribute(ExifInterface.TAG_DATETIME_ORIGINAL))
        assertNull(exif.getAttribute(ExifInterface.TAG_GPS_LATITUDE))
    }

    @Test
    fun prepareForUpload_smallPhoto_isSentUnchanged() {
        val original = photo(1600, 1200)

        val result = prepareForUpload(original, "image/jpeg", cacheDir)

        assertArrayEquals(original, result.bytes)
    }

    @Test
    fun prepareForUpload_undecodableBytes_areSentUnchanged() {
        val original = byteArrayOf(1, 2, 3)

        val result = prepareForUpload(original, "image/heic", cacheDir)

        assertArrayEquals(original, result.bytes)
        assertEquals("image/heic", result.mimeType)
    }
}
