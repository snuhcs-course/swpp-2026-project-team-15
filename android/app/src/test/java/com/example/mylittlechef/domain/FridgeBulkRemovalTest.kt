// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.domain

import org.junit.Assert.assertEquals
import org.junit.Test

class FridgeBulkRemovalTest {
    @Test fun bulkRemovalUsesExactIdentityAndPreservesKeptArrivalOrder() {
        val inventory = FridgeInventory(listOf("마늘", "다진마늘", "Kimchi", "두부", "소금"))
        assertEquals(listOf("다진마늘", "Kimchi", "소금"),
            inventory.removeAll(setOf("마늘", "두부", "kimchi")).names)
    }
}
