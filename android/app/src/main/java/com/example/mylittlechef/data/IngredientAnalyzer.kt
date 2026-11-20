// AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data

import android.content.Context
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.core.net.toFile
import com.example.mylittlechef.data.remote.AnalyzeResponse
import com.example.mylittlechef.data.remote.ApiClient
import com.example.mylittlechef.data.remote.MultiImageApi
import com.example.mylittlechef.data.remote.MyLittleChefApi
import com.example.mylittlechef.data.remote.toIngredient
import com.example.mylittlechef.data.remote.RecognitionReviewApi
import com.example.mylittlechef.data.remote.toPhotoAnalysis
import com.example.mylittlechef.domain.PhotoAnalysis
import com.example.mylittlechef.domain.sweep.SweepFiles
import com.example.mylittlechef.model.Ingredient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.withTimeoutOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.HttpException
import java.io.File

class IngredientAnalyzer(
    private val context: Context,
    private val api: MyLittleChefApi = ApiClient.api,
    private val multiImageApi: MultiImageApi = ApiClient.multiImageApi,
    private val reviewApi: RecognitionReviewApi? = ApiClient.recognitionReviewApi
) {
    /**
     * Returns unconfirmed candidates, or null when the photo could not be analyzed.
     * A video-mode preview frame ([SweepFiles]) sends all frames of its sweep in one request;
     * anything else is sent as a single photo, as before.
     */
    suspend fun analyze(imageUri: Uri): List<Ingredient>? = try {
        val frames = sweepFrames(imageUri)
        val response = if (frames == null) analyzeOne(imageUri) else analyzeViews(frames, imageUri)
        response.candidates.map { it.toIngredient() }
    } catch (cancelled: CancellationException) { throw cancelled }
    catch (_: Exception) { null }

    /** Capabilities are a free GET. Never retry a provider failure through another endpoint. */
    suspend fun review(imageUri: Uri): PhotoAnalysis {
        val capabilities = try {
            withTimeoutOrNull(3_000) { reviewApi?.capabilities() }
        } catch (error: HttpException) {
            if (error.code() in setOf(404, 405)) null else throw error
        }
        val frames = sweepFrames(imageUri)
        val uris = frames?.map { Uri.fromFile(it).toString() } ?: listOf(imageUri.toString())
        val parts = if (frames == null) listOf(singlePart(imageUri)) else viewParts(frames)
        val reviewTypes = capabilities?.reviewImageTypes?.map { it.lowercase() }?.toSet() ?: REVIEW_IMAGE_TYPES
        val compatible = parts.all { part ->
            part.body.contentType()?.let { "${it.type}/${it.subtype}" } in reviewTypes
        }
        if (capabilities?.reviewSupported == true && reviewApi != null && compatible) {
            val response = if (frames == null) reviewApi.analyzePhoto(parts.single())
                else reviewApi.analyzeViews(parts)
            return response.toPhotoAnalysis(uris, capabilities.providerMode)
        }
        if (frames == null) return api.analyze(parts.single()).toPhotoAnalysis(uris, capabilities?.providerMode)
        return try {
            multiImageApi.analyzeViews(parts).toPhotoAnalysis(uris, capabilities?.providerMode)
        } catch (error: HttpException) {
            if (error.code() !in FALLBACK_CODES) throw error
            val preview = MultipartBody.Part.createFormData("image", "photo", parts.first().body)
            api.analyze(preview).toPhotoAnalysis(listOf(imageUri.toString()), capabilities?.providerMode)
        }
    }

    private fun sweepFrames(imageUri: Uri): List<File>? =
        if (imageUri.scheme == "file") SweepFiles.framesFor(imageUri.toFile()) else null

    private suspend fun analyzeOne(imageUri: Uri): AnalyzeResponse {
        return api.analyze(singlePart(imageUri))
    }

    private suspend fun singlePart(imageUri: Uri): MultipartBody.Part {
        val image = withContext(Dispatchers.IO) {
            val resolver = context.contentResolver
            val original = checkNotNull(resolver.openInputStream(imageUri)).use { it.readBytes() }
            prepareChecked(original)
        }
        return MultipartBody.Part.createFormData(
            "image", "photo", image.bytes.toRequestBody(image.mimeType.toMediaType())
        )
    }

    private suspend fun viewParts(frames: List<File>): List<MultipartBody.Part> = withContext(Dispatchers.IO) {
        frames.mapIndexed { position, file ->
            val image = prepareChecked(file.readBytes())
            MultipartBody.Part.createFormData("images", "view-%02d".format(position),
                image.bytes.toRequestBody(image.mimeType.toMediaType()))
        }
    }

    private fun prepareChecked(original: ByteArray): UploadImage {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeByteArray(original, 0, original.size, bounds)
        val actualType = bounds.outMimeType?.lowercase()
        require(actualType in LEGACY_IMAGE_TYPES) { "Unsupported or invalid photo format" }
        val upload = prepareForUpload(original, actualType, context.cacheDir)
        val bitmap = requireNotNull(BitmapFactory.decodeByteArray(upload.bytes, 0, upload.bytes.size)) {
            "Photo cannot be decoded"
        }
        bitmap.recycle()
        return upload
    }

    private suspend fun analyzeViews(frames: List<File>, preview: Uri): AnalyzeResponse {
        val parts = viewParts(frames)
        return try {
            multiImageApi.analyzeViews(parts)
        } catch (e: HttpException) {
            // A server without multi-image support rejects the field; the preview frame is a valid photo.
            if (e.code() in FALLBACK_CODES) analyzeOne(preview) else throw e
        }
    }

    private companion object {
        val FALLBACK_CODES = setOf(400, 404, 405, 415, 422)
        val REVIEW_IMAGE_TYPES = setOf("image/jpeg", "image/png", "image/webp")
        val LEGACY_IMAGE_TYPES = REVIEW_IMAGE_TYPES + setOf("image/heic", "image/heif")
    }
}
