package com.example.mylittlechef.integration

import androidx.test.platform.app.InstrumentationRegistry
import com.example.mylittlechef.BuildConfig
import com.example.mylittlechef.data.remote.*
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Assume.assumeTrue
import org.junit.Test

/** Only opt in against the local mock server; never exercises a paid provider. */
class OnDemandApiTest {
    @Test fun catalogOriginalListAndExplicitMockRevisionRoundTrip() = runBlocking {
        assumeTrue(InstrumentationRegistry.getArguments().getString("localMock") == "true")
        assertEquals("http://127.0.0.1:8000/", BuildConfig.SERVER_BASE_URL)
        // Optional legacy local API is deliberately separate from the deployed default client.
        val api = retrofit2.Retrofit.Builder().baseUrl(BuildConfig.SERVER_BASE_URL)
            .addConverterFactory(retrofit2.converter.gson.GsonConverterFactory.create())
            .build().create(FullRecipeApi::class.java)
        val names = setOf("계란","밥","두부","김치","대파")
        val ids = api.recipeCatalog().items.filter { it.name in names }.map { it.id }
        assertEquals(5,ids.size)
        val candidates = api.candidates(InventoryIdsDto(ids)).recipes
        assertTrue(candidates.isNotEmpty())
        assertTrue(candidates.all { it.revisionCandidate == it.missing.isNotEmpty() })
        val selected = candidates.first { it.revisionCandidate }
        val response = api.reviseRecipe(selected.id, InventoryIdsDto(ids))
        assertEquals(selected.id,response.id)
        assertEquals(selected.original,response.original)
        assertEquals("refused",response.revision.status)
        assertTrue(response.revision.result!!.reason.contains("MOCK ONLY"))
    }
}
