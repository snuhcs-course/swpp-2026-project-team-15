// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.local.AppDataReset
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class DataResetViewModelTest {
    private lateinit var dispatcher: kotlinx.coroutines.test.TestDispatcher

    @Before fun setUp() { dispatcher = StandardTestDispatcher(); Dispatchers.setMain(dispatcher) }
    @After fun tearDown() { Dispatchers.resetMain() }

    private class FakeReset(var failure: Exception? = null, val gate: CompletableDeferred<Unit>? = null) : AppDataReset {
        var calls = 0
        override suspend fun resetAll() {
            calls++
            gate?.await()
            failure?.let { throw it }
        }
    }

    @Test fun successRunsTheCallbackAfterTheReset() = runTest(dispatcher) {
        val fake = FakeReset()
        val vm = DataResetViewModel(fake)
        var done = 0
        vm.resetAll { done++ }
        assertTrue(vm.isResetting)
        advanceUntilIdle()
        assertEquals(1, fake.calls)
        assertEquals(1, done)
        assertFalse(vm.isResetting)
        assertNull(vm.error)
    }

    @Test fun failureShowsAnErrorAndDoesNotNavigate() = runTest(dispatcher) {
        val fake = FakeReset(failure = IOException("disk"))
        val vm = DataResetViewModel(fake)
        var done = 0
        vm.resetAll { done++ }
        advanceUntilIdle()
        assertEquals(0, done)
        assertEquals("초기화하지 못했어요. 다시 시도해 주세요.", vm.error)
        assertFalse(vm.isResetting)
        vm.dismissError()
        assertNull(vm.error)
        fake.failure = null
        vm.resetAll { done++ }
        advanceUntilIdle()
        assertEquals(1, done)
        assertNull(vm.error)
    }

    @Test fun aSecondTapWhileRunningIsIgnored() = runTest(dispatcher) {
        val gate = CompletableDeferred<Unit>()
        val fake = FakeReset(gate = gate)
        val vm = DataResetViewModel(fake)
        var done = 0
        vm.resetAll { done++ }
        advanceUntilIdle()
        vm.resetAll { done++ }
        gate.complete(Unit)
        advanceUntilIdle()
        assertEquals(1, fake.calls)
        assertEquals(1, done)
    }
}
