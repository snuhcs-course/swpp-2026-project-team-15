// AI-generated with Claude Code (Opus 5.5), 2026-10-11; review pending by Jaehyuk Choi.
package com.example.mylittlechef.data

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import com.example.mylittlechef.data.remote.ApiClient
import com.example.mylittlechef.data.remote.MyLittleChefApi
import com.example.mylittlechef.data.remote.toIngredient
import com.example.mylittlechef.model.Ingredient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.ByteArrayOutputStream

private const val MAX_IMAGE_SIDE = 1024
private const val JPEG_QUALITY = 85

class IngredientAnalyzer(
    private val context: Context,
    private val api: MyLittleChefApi = ApiClient.api
) {
    /** Returns unconfirmed candidates, or null when the photo could not be analyzed. */
    suspend fun analyze(imageUri: Uri): List<Ingredient>? = runCatching {
        val jpeg = withContext(Dispatchers.IO) { readDownscaledJpeg(imageUri) }
        val part = MultipartBody.Part.createFormData(
            "image", "photo.jpg", jpeg.toRequestBody("image/jpeg".toMediaType())
        )
        api.analyze(part).candidates.map { it.toIngredient() }
    }.getOrNull()

    // Smaller uploads keep the request fast and the recognition token cost low.
    private fun readDownscaledJpeg(uri: Uri): ByteArray {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        context.contentResolver.openInputStream(uri).use { BitmapFactory.decodeStream(it, null, bounds) }

        var sampleSize = 1
        while (maxOf(bounds.outWidth, bounds.outHeight) / (sampleSize * 2) >= MAX_IMAGE_SIDE) {
            sampleSize *= 2
        }
        val bitmap = context.contentResolver.openInputStream(uri).use {
            BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = sampleSize })
        } ?: error("Unreadable image: $uri")

        return ByteArrayOutputStream().use { output ->
            bitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, output)
            output.toByteArray()
        }
    }
}
