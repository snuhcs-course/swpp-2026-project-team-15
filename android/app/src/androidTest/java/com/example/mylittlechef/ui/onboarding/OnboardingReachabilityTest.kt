// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui.onboarding

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.requiredSize
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.isImeVisible
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.unit.dp
import com.example.mylittlechef.model.Preset
import com.example.mylittlechef.viewmodel.UserViewModel
import com.example.mylittlechef.ui.theme.MyLittleChefTheme
import org.junit.Assert.assertTrue
import org.junit.Assert.assertEquals
import org.junit.Rule
import org.junit.Test

class OnboardingReachabilityTest {
    @get:Rule val rule = createComposeRule()

    @Test fun pantryChoicesFitPhoneAndExposeCheckboxState() {
        var selected by mutableStateOf(emptyList<String>())
        rule.setContent {
            MaterialTheme {
                Box(Modifier.requiredSize(360.dp, 720.dp)) {
                    OnboardingPantry(selected, { selected = it }, {}, {})
                }
            }
        }
        val nextTop = rule.onNodeWithText("다음").getUnclippedBoundsInRoot().top
        (Preset.pantrySeasonings + Preset.pantryBasics).forEach { name ->
            val choice = rule.onNodeWithText(name)
            choice.assertIsDisplayed().assertIsOff()
            choice.assertHeightIsAtLeast(48.dp)
            assertTrue(choice.getUnclippedBoundsInRoot().bottom <= nextTop)
        }
        rule.onNodeWithText("소금").performClick().assertIsOn()
        rule.onNodeWithText("설탕").assertIsOff()
        rule.onNodeWithText("소금").performClick().assertIsOff()
    }

    @Test fun shortScreenScrollsChoicesWithoutMovingNext() {
        rule.setContent {
            MaterialTheme {
                Box(Modifier.requiredSize(320.dp, 480.dp)) {
                    OnboardingPantry(emptyList(), {}, {}, {})
                }
            }
        }
        val original = rule.onNodeWithText("다음").getUnclippedBoundsInRoot()
        rule.onNodeWithText("김치").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("다음").assertIsDisplayed()
        assertTrue(rule.onNodeWithText("다음").getUnclippedBoundsInRoot() == original)
    }

    @Test fun largeFontKeepsLastChoiceSelectableAndNextFixedOnShortScreen() {
        var selected by mutableStateOf(emptyList<String>())
        rule.setContent {
            val deviceDensity = LocalDensity.current.density
            CompositionLocalProvider(LocalDensity provides Density(deviceDensity, fontScale = 1.7f)) {
                MaterialTheme {
                    Box(Modifier.requiredSize(320.dp, 480.dp)) {
                        OnboardingPantry(selected, { selected = it }, {}, {})
                    }
                }
            }
        }
        val originalNextBounds = rule.onNodeWithText("다음").getUnclippedBoundsInRoot()
        rule.onNodeWithText("김치").performScrollTo().assertIsDisplayed().assertIsOff()
            .assertHeightIsAtLeast(48.dp).performClick().assertIsOn()
        rule.runOnIdle { assertEquals(listOf("김치"), selected) }
        rule.onNodeWithText("다음").assertIsDisplayed().assertHeightIsAtLeast(48.dp)
        assertEquals(originalNextBounds, rule.onNodeWithText("다음").getUnclippedBoundsInRoot())
    }

    @OptIn(ExperimentalLayoutApi::class)
    @Test fun nicknameAndNextRemainUsableWithTheRealSoftwareKeyboardOpen() {
        val user=UserViewModel()
        var imeVisible=false
        var advanced=false
        rule.setContent {
            MyLittleChefTheme {
                imeVisible=WindowInsets.isImeVisible
                OnboardingNickname(user) { advanced=true }
            }
        }
        rule.onNode(hasSetTextAction()).performClick().performTextInput("키보드 확인")
        rule.waitUntil(10_000) { imeVisible }
        rule.onNode(hasSetTextAction()).assertIsDisplayed()
        rule.onNodeWithText("다음").assertIsDisplayed().performClick()
        rule.runOnIdle { assertTrue(advanced); assertEquals("키보드 확인",user.nickname) }
    }
}
