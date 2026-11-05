// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.data.remote

import org.junit.Assert.assertFalse
import org.junit.Test

class DeployedApiContractTest {
    @Test fun defaultClientDoesNotRequireUnpublishedOnDemandRoutes() {
        assertFalse("Deployed main has no ingredient-catalog/candidates/single revision routes",
            ApiClient.api is OnDemandRecipeApi)
    }
}
