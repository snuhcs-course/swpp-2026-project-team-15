// AI-assisted local-only free transport regression, 2026-11-10; human review pending.
package com.example.mylittlechef.integration

import com.example.mylittlechef.BuildConfig
import com.example.mylittlechef.data.remote.ApiClient
import com.example.mylittlechef.data.remote.RecommendRequest
import kotlinx.coroutines.*
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test

/** Requires the loopback mock server and adb reverse; never calls a model/revision POST. */
class HeSelectedTransportTest {
    @Test fun idleRecipeConnectionDoesNotBreakTheFirstFreeCapabilityProbe()=runBlocking {
        assumeTrue(BuildConfig.SERVER_BASE_URL == "http://127.0.0.1:8000/")
        withContext(Dispatchers.IO) {
            ApiClient.api.recommend(RecommendRequest(listOf("두부","김치","대파")))
            delay(8_000) // Existing local Uvicorn closes its idle keep-alive socket after five seconds.
            assertTrue(ApiClient.selectedRecipeApi.selectedCapabilities().supported)
        }
    }
}
