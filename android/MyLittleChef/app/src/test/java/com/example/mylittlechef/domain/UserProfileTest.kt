package com.example.mylittlechef.domain

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class UserProfileTest {
    @Test fun selections_areUniqueAndTrimmed() {
        val profile = UserProfile().withUtensils(listOf(" 냄비 ", "냄비", "")).withAllergies(listOf("우유", " 우유 "))
        assertEquals(listOf("냄비"), profile.utensils)
        assertEquals(listOf("우유"), profile.allergies)
    }

    @Test fun likes_doNotDuplicateAndCanBeRemoved() {
        val profile = UserProfile().like(12).like(12).unlike(12)
        assertEquals(emptyList<Long>(), profile.likes)
        assertFalse(profile.onboardingComplete)
        assertTrue(profile.copy(onboardingComplete = true).onboardingComplete)
    }
}
