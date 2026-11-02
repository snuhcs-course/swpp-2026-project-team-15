// AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data

import android.content.Context
import android.net.Uri
import androidx.core.net.toFile
import com.example.mylittlechef.data.remote.AnalyzeResponse
import com.example.mylittlechef.data.remote.ApiClient
import com.example.mylittlechef.data.remote.MultiImageApi
import com.example.mylittlechef.data.remote.MyLittleChefApi
import com.example.mylittlechef.data.remote.toIngredient
import com.example.mylittlechef.domain.sweep.SweepFiles
import com.example.mylittlechef.model.Ingredient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.HttpException
import java.io.File

class IngredientAnalyzer(
    private val context: Context,
    private val api: MyLittleChefApi = ApiClient.api,
    private val multiImageApi: MultiImageApi = ApiClient.multiImageApi
) {
    /**
     * Returns unconfirmed candidates, or null when the photo could not be analyzed.
     * A video-mode preview frame ([SweepFiles]) sends all frames of its sweep in one request;
     * anything else is sent as a single photo, as before.
     */
    suspend fun analyze(imageUri: Uri): List<Ingredient>? = runCatching {
        val frames = sweepFrames(imageUri)
        val response = if (frames == null) analyzeOne(imageUri) else analyzeViews(frames, imageUri)
        response.candidates.map { it.toIngredient() }
    }.getOrNull()

    private fun sweepFrames(imageUri: Uri): List<File>? =
        if (imageUri.scheme == "file") SweepFiles.framesFor(imageUri.toFile()) else null

    private suspend fun analyzeOne(imageUri: Uri): AnalyzeResponse {
        val image = withContext(Dispatchers.IO) {
            val resolver = context.contentResolver
            val original = checkNotNull(resolver.openInputStream(imageUri)).use { it.readBytes() }
            prepareForUpload(original, resolver.getType(imageUri), context.cacheDir)
        }
        val part = MultipartBody.Part.createFormData(
            "image", "photo", image.bytes.toRequestBody(image.mimeType.toMediaType())
        )
        return api.analyze(part)
    }

    private suspend fun analyzeViews(frames: List<File>, preview: Uri): AnalyzeResponse {
        val parts = withContext(Dispatchers.IO) {
            frames.mapIndexed { position, file ->
                val image = prepareForUpload(file.readBytes(), "image/jpeg", context.cacheDir)
                MultipartBody.Part.createFormData(
                    "images", "view-%02d".format(position), image.bytes.toRequestBody(image.mimeType.toMediaType())
                )
            }
        }
        return try {
            multiImageApi.analyzeViews(parts)
        } catch (e: HttpException) {
            // A server without multi-image support rejects the field; the preview frame is a valid photo.
            if (e.code() in FALLBACK_CODES) analyzeOne(preview) else throw e
        }
    }

    private companion object {
        val FALLBACK_CODES = setOf(400, 404, 405, 415, 422)
    }
}
