// AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.ui.recipe

import com.example.mylittlechef.domain.Availability
import org.junit.Assert.assertEquals
import org.junit.Test

class AvailabilityLabelTest {
    // User request (2026-11-19): each recipe row shows in words whether the user has it. Since the #24 recipe
    // UI (2026-11-20) the words are its chips, with "기본 양념" for what is assumed at home.
    @Test
    fun everyStateHasItsOwnWord() {
        val labels = Availability.entries.associateWith(::availabilityLabel)
        assertEquals("준비됨", labels[Availability.OWNED])
        assertEquals("기본 양념", labels[Availability.ASSUMED])
        assertEquals("부족", labels[Availability.UNAVAILABLE])
    }
}
