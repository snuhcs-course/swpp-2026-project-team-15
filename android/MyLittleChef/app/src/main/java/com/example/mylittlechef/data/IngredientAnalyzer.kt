// AI-generated with Claude Code (Opus 5.5), 2026-10-11 to 2026-10-14; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data

import android.content.Context
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

class IngredientAnalyzer(
    private val context: Context,
    private val api: MyLittleChefApi = ApiClient.api
) {
    /** Returns unconfirmed candidates, or null when the photo could not be analyzed. */
    suspend fun analyze(imageUri: Uri): List<Ingredient>? = runCatching {
        val image = withContext(Dispatchers.IO) {
            val resolver = context.contentResolver
            val original = checkNotNull(resolver.openInputStream(imageUri)).use { it.readBytes() }
            prepareForUpload(original, resolver.getType(imageUri), context.cacheDir)
        }
        val part = MultipartBody.Part.createFormData(
            "image", "photo", image.bytes.toRequestBody(image.mimeType.toMediaType())
        )
        api.analyze(part).candidates.map { it.toIngredient() }
    }.getOrNull()
}
