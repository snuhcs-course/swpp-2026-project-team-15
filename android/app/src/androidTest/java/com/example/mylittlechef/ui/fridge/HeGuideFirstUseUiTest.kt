// AI-assisted HE first-use regressions, 2026-11-09; manual review pending.
package com.example.mylittlechef.ui.fridge

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import androidx.test.platform.app.InstrumentationRegistry
import com.example.mylittlechef.data.local.UsageGuideRepository
import com.example.mylittlechef.ui.help.FirstUseGuide
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test
import java.io.File

class HeGuideFirstUseUiTest {
    @get:Rule val rule = createComposeRule()
    @Test fun guideWaitsForOnboardingAndStaysDismissedWhenReopened() {
        val context = InstrumentationRegistry.getInstrumentation().targetContext
        val file = File.createTempFile("guide-test", ".preferences_pb", context.cacheDir).apply { delete() }
        val job = SupervisorJob()
        val repository = UsageGuideRepository(PreferenceDataStoreFactory.create(
            scope = CoroutineScope(Dispatchers.IO + job), produceFile = { file }))
        val enabled = mutableStateOf(false)
        try {
            rule.setContent { MaterialTheme { FirstUseGuide(repository, enabled.value) } }
            rule.onNodeWithTag("usage-guide").assertDoesNotExist()
            rule.runOnIdle { enabled.value = true }
            rule.waitUntil(5000) { rule.onAllNodesWithTag("usage-guide").fetchSemanticsNodes().isNotEmpty() }
            rule.onNodeWithTag("close-usage-guide").performClick()
            rule.waitUntil(5000) { rule.onAllNodesWithTag("usage-guide").fetchSemanticsNodes().isEmpty() }
            rule.runOnIdle { enabled.value = false }
            rule.runOnIdle { enabled.value = true }
            rule.onNodeWithTag("usage-guide").assertDoesNotExist()
            runBlocking { assertEquals(1, repository.seenVersion.first()) }
        } finally { runBlocking { job.cancelAndJoin() }; file.delete() }
    }
}
