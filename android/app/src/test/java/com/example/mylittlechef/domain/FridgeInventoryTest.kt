package com.example.mylittlechef.domain

import org.junit.Assert.assertEquals
import org.junit.Test

class FridgeInventoryTest {
    @Test fun bulkRemovalUsesExactIdentityAndPreservesKeptArrivalOrder() {
        val inventory = FridgeInventory(listOf("마늘", "다진마늘", "Kimchi", "두부", "소금"))
        assertEquals(listOf("다진마늘", "Kimchi", "소금"),
            inventory.removeAll(setOf("마늘", "두부", "kimchi")).names)
    }
    @Test fun add_normalizesAndDeduplicatesNames() {
        val inventory = FridgeInventory().addAll(listOf("  두부 ", "", "두부", "Kimchi", "kimchi"))
        assertEquals(listOf("두부", "Kimchi"), inventory.names)
    }

    @Test fun remove_usesNormalizedName() {
        val inventory = FridgeInventory().addAll(listOf("두부", "김치")).remove(" 김치 ")
        assertEquals(listOf("두부"), inventory.names)
    }
}
