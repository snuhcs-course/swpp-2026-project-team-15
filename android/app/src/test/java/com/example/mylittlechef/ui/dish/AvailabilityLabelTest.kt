// AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.ui.dish

import com.example.mylittlechef.domain.Availability
import org.junit.Assert.assertEquals
import org.junit.Test

class AvailabilityLabelTest {
    // User request (2026-11-19): each recipe row shows in words whether the user has it.
    @Test
    fun everyStateHasItsOwnWord() {
        val labels = Availability.entries.associateWith(::availabilityLabel)
        assertEquals("있음", labels[Availability.OWNED])
        assertEquals("기본 양념", labels[Availability.ASSUMED])
        assertEquals("없음", labels[Availability.UNAVAILABLE])
    }
}
