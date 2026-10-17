package com.example.mylittlechef.domain

import org.junit.Assert.assertEquals
import org.junit.Test

class FridgeInventoryTest {
    @Test fun add_normalizesAndDeduplicatesNames() {
        val inventory = FridgeInventory().addAll(listOf("  두부 ", "", "두부", "Kimchi", "kimchi"))
        assertEquals(listOf("두부", "Kimchi"), inventory.names)
    }

    @Test fun remove_usesNormalizedName() {
        val inventory = FridgeInventory().addAll(listOf("두부", "김치")).remove(" 김치 ")
        assertEquals(listOf("두부"), inventory.names)
    }
}
