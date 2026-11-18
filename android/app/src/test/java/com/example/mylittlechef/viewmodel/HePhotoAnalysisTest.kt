// AI-assisted HE photo state regressions, 2026-11-09; manual review pending.
package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.domain.*
import com.example.mylittlechef.model.Ingredient
import com.example.mylittlechef.data.remote.*
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException

@OptIn(ExperimentalCoroutinesApi::class)
class HePhotoAnalysisTest {
    @Test fun reviewEvidenceSurvivesEditingAndMustBeConfirmedAgain() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val response = AnalyzeResponse(listOf(IngredientCandidateDto("두부", listOf("흰색 포장"), .4)))
            val vm = PhotoAnalysisViewModel { response.toPhotoAnalysis(listOf(it)) }
            vm.start("photo")
            advanceUntilIdle()
            assertTrue(vm.state is PhotoAnalysisState.Ready)
            val evidence = vm.editor.ingredients.single().recognition!!
            assertEquals(.4, evidence.confidence!!, .001)
            assertTrue(evidence.needsReview)
            assertFalse(vm.confirmed)
            vm.confirm(true)
            assertTrue(vm.confirmed)
            vm.editor.rename(0, "순두부")
            assertFalse(vm.confirmed)
            assertEquals("두부", vm.editor.ingredients.single().recognition!!.suggestedName)
        } finally { Dispatchers.resetMain() }
    }

    @Test fun lateResponseAfterCancelCannotReplaceANewerPhoto() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        val old = CompletableDeferred<Unit>()
        try {
            val vm = PhotoAnalysisViewModel { uri ->
                if (uri == "old") withContext(NonCancellable) { old.await() }
                PhotoAnalysis(listOf(Ingredient(uri)), listOf(uri))
            }
            vm.start("old")
            vm.cancel()
            assertEquals(PhotoAnalysisState.Cancelled, vm.state)
            vm.start("new")
            old.complete(Unit)
            advanceUntilIdle()
            assertEquals(listOf("new"), vm.editor.ingredients.map { it.name })
            assertEquals(listOf("new"), (vm.state as PhotoAnalysisState.Ready).result.imageUris)
        } finally { old.complete(Unit); advanceUntilIdle(); Dispatchers.resetMain() }
    }

    @Test fun emptyAndNetworkErrorHaveDifferentStatesAndRetryIsExplicit() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            var calls = 0
            val vm = PhotoAnalysisViewModel {
                calls++
                if (calls == 1) throw IOException("private transport detail")
                PhotoAnalysis(emptyList(), listOf(it))
            }
            vm.start("photo")
            advanceUntilIdle()
            assertTrue(vm.state is PhotoAnalysisState.Failed)
            assertFalse((vm.state as PhotoAnalysisState.Failed).message.contains("private"))
            vm.start("photo")
            assertEquals(1, calls)
            vm.retry()
            advanceUntilIdle()
            assertTrue(vm.state is PhotoAnalysisState.Empty)
            assertEquals(2, calls)
        } finally { Dispatchers.resetMain() }
    }
}
