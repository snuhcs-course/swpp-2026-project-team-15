// AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data

import com.example.mylittlechef.data.remote.AnalyzeResponse
import com.example.mylittlechef.data.remote.RecognitionCapabilitiesDto
import com.example.mylittlechef.data.remote.RecognitionReviewApi
import kotlinx.coroutines.test.runTest
import okhttp3.MultipartBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import java.io.IOException

/**
 * The first gallery pick after a pause failed with a network message and no photo was sent: the
 * optional capability GET hit a connection the server had already closed (emulator E2E, 2026-11-20).
 */
class OptionalCapabilitiesTest {
    private class Api(private val answer: () -> RecognitionCapabilitiesDto) : RecognitionReviewApi {
        override suspend fun capabilities() = answer()
        override suspend fun analyzePhoto(image: MultipartBody.Part): AnalyzeResponse = error("unused")
        override suspend fun analyzeViews(images: List<MultipartBody.Part>): AnalyzeResponse = error("unused")
    }

    @Test fun aNetworkFailureMeansUnknownCapabilitiesNotAFailedPick() = runTest {
        assertNull(optionalCapabilities(Api { throw IOException("unexpected end of stream") }))
    }

    @Test fun knownCapabilitiesArePassedThrough() = runTest {
        val dto = RecognitionCapabilitiesDto(reviewSupported = true)
        assertEquals(dto, optionalCapabilities(Api { dto }))
        assertNull(optionalCapabilities(null))
    }

    @Test fun idleConnectionsAreDroppedBeforeTheServersSixtyFiveSecondLimit() {
        assertEquals(true, com.example.mylittlechef.data.remote.IDLE_CONNECTION_SECONDS < 65)
    }
}
