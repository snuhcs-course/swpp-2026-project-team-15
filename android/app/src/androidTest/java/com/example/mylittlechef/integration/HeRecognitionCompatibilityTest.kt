// AI-assisted HE transport compatibility tests, 2026-11-09; manual review pending.
package com.example.mylittlechef.integration

import android.graphics.Bitmap
import android.net.Uri
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mylittlechef.data.IngredientAnalyzer
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.domain.RecognitionMode
import kotlinx.coroutines.runBlocking
import okhttp3.MultipartBody
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.*
import org.junit.Test
import retrofit2.HttpException
import retrofit2.Response
import java.io.File

class HeRecognitionCompatibilityTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext
    private val response get() = AnalyzeResponse(listOf(IngredientCandidateDto("두부", listOf("포장 두부"), .5)))
    private fun http(code: Int) = HttpException(Response.error<Any>(code, "{}".toResponseBody()))

    private fun writePhoto(file: File): File {
        val bitmap = Bitmap.createBitmap(24, 24, Bitmap.Config.ARGB_8888)
        bitmap.eraseColor(android.graphics.Color.GREEN)
        file.outputStream().use { bitmap.compress(Bitmap.CompressFormat.PNG, 100, it) }
        bitmap.recycle()
        return file
    }

    private class Calls { var capabilities = 0; var review = 0; var legacy = 0; var multi = 0 }

    private fun analyzer(calls: Calls, capabilityCode: Int? = null, reviewCode: Int? = null,
        multiCode: Int? = null): IngredientAnalyzer {
        val legacy = object : MyLittleChefApi {
            override suspend fun analyze(image: MultipartBody.Part): AnalyzeResponse { calls.legacy++; return response }
            override suspend fun recommend(request: RecommendRequest) = error("Not used")
        }
        val multi = object : MultiImageApi {
            override suspend fun analyzeViews(images: List<MultipartBody.Part>): AnalyzeResponse {
                calls.multi++
                if (multiCode != null) throw http(multiCode)
                return response
            }
        }
        val review = object : RecognitionReviewApi {
            override suspend fun capabilities(): RecognitionCapabilitiesDto {
                calls.capabilities++
                if (capabilityCode != null) throw http(capabilityCode)
                return RecognitionCapabilitiesDto(true, "mock", false)
            }
            override suspend fun analyzePhoto(image: MultipartBody.Part): AnalyzeResponse {
                calls.review++
                if (reviewCode != null) throw http(reviewCode)
                return response.copy(review = AnalysisReviewDto(providerMode = "mock", imageCount = 1))
            }
            override suspend fun analyzeViews(images: List<MultipartBody.Part>) = analyzePhoto(images.first())
        }
        return IngredientAnalyzer(context, legacy, multi, review)
    }

    @Test fun legacyServerWithoutCapabilitiesUsesExactlyOneLegacyPhotoRequest() = runBlocking {
        val file = writePhoto(File.createTempFile("legacy-he", ".png", context.cacheDir))
        try {
            val calls = Calls()
            val result = analyzer(calls, capabilityCode = 404).review(Uri.fromFile(file))
            assertEquals(1, calls.capabilities); assertEquals(1, calls.legacy); assertEquals(0, calls.review)
            assertEquals(RecognitionMode.UNKNOWN, result.mode)
            assertTrue(result.candidates.single().recognition!!.needsReview)
        } finally { file.delete() }
    }

    @Test fun supportedServerUsesReviewButProviderFailuresNeverTriggerALegacyRetry() = runBlocking {
        val file = writePhoto(File.createTempFile("review-he", ".png", context.cacheDir))
        try {
            val success = Calls()
            assertEquals(RecognitionMode.MOCK, analyzer(success).review(Uri.fromFile(file)).mode)
            assertEquals(1, success.review); assertEquals(0, success.legacy)
            val failed = Calls()
            try { analyzer(failed, reviewCode = 503).review(Uri.fromFile(file)); fail("Expected 503") }
            catch (expected: HttpException) { assertEquals(503, expected.code()) }
            assertEquals(1, failed.review); assertEquals(0, failed.legacy)
        } finally { file.delete() }
    }

    @Test fun genuineSmallHeicUsesLegacyBeforeAnyUnsupportedReviewCall() = runBlocking {
        val encoded = InstrumentationRegistry.getInstrumentation().context.assets
            .open("he-synthetic.heic.b64").bufferedReader().use { it.readText() }
        val bytes = android.util.Base64.decode(encoded, android.util.Base64.DEFAULT)
        val bitmap = android.graphics.BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
        assertNotNull("The fixture must be a decodable genuine HEIC image", bitmap)
        bitmap!!.recycle()
        val file = File.createTempFile("small-he", ".heic", context.cacheDir).apply { writeBytes(bytes) }
        try {
            val calls = Calls()
            val result = analyzer(calls, reviewCode = 415).review(Uri.fromFile(file))
            assertEquals(1, calls.legacy)
            assertEquals(0, calls.review)
            assertEquals(RecognitionMode.MOCK, result.mode)
        } finally { file.delete() }
    }

    @Test fun invalidFileNeverReachesRecognitionAndUnsupportedMultiUsesOnlyThePreview() = runBlocking {
        val invalid = File.createTempFile("invalid-he", ".png", context.cacheDir).apply { writeText("not an image") }
        val directory = File(context.cacheDir, "sweep-${System.currentTimeMillis()}")
        check(directory.mkdir())
        val first = writePhoto(File(directory, "frame-00.jpg"))
        val second = writePhoto(File(directory, "frame-01.jpg"))
        try {
            val bad = Calls()
            try { analyzer(bad).review(Uri.fromFile(invalid)); fail("Invalid image must fail") }
            catch (_: IllegalArgumentException) { }
            assertEquals(0, bad.review); assertEquals(0, bad.legacy)
            val old = Calls()
            val result = analyzer(old, capabilityCode = 404, multiCode = 422).review(Uri.fromFile(first))
            assertEquals(1, old.multi); assertEquals(1, old.legacy)
            assertEquals(listOf(Uri.fromFile(first).toString()), result.imageUris)
        } finally { invalid.delete(); first.delete(); second.delete(); directory.delete() }
    }
}
