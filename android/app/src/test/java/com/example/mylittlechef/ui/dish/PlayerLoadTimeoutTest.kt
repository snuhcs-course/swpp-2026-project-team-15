// AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.ui.dish

import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Test

/** Integrity review (2026-11-20): a player page that never loads shows the in-app notice again. */
@OptIn(ExperimentalCoroutinesApi::class)
class PlayerLoadTimeoutTest {
    @Test fun aPlayerThatNeverBecomesReadyIsReportedOnce() = runTest {
        var reports = 0
        launch { reportIfNotReady({ false }, LOAD_TIMEOUT_MS) { reports++ } }
        advanceTimeBy(LOAD_TIMEOUT_MS - 1); runCurrent()
        assertEquals(0, reports)
        advanceTimeBy(2); runCurrent()
        assertEquals(1, reports)
    }

    @Test fun aReadyPlayerIsNotReported() = runTest {
        var reports = 0
        launch { reportIfNotReady({ true }, LOAD_TIMEOUT_MS) { reports++ } }
        advanceTimeBy(LOAD_TIMEOUT_MS + 1); runCurrent()
        assertEquals(0, reports)
    }
}
