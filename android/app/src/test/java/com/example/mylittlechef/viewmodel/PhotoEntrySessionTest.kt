// Entry lifecycle regressions assisted by Codex, 2026-11-19; human review pending.
package com.example.mylittlechef.viewmodel
import com.example.mylittlechef.domain.*
import com.example.mylittlechef.model.Ingredient
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test
@OptIn(ExperimentalCoroutinesApi::class)
class PhotoEntrySessionTest {
    @Test fun sameEntryDoesNotDuplicateButReopeningSamePhotoStartsAgain() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            var calls=0
            val model=PhotoAnalysisViewModel { calls++;PhotoAnalysis(listOf(Ingredient("두부")),listOf(it)) }
            model.startEntry("photo","first");advanceUntilIdle()
            model.editor.rename(0,"순두부")
            model.startEntry("photo","first");advanceUntilIdle()
            assertEquals(1,calls);assertEquals("순두부",model.editor.ingredients.single().name)
            model.cancel()
            model.startEntry("photo","second");advanceUntilIdle()
            assertEquals(2,calls);assertEquals("두부",model.editor.ingredients.single().name)
            assertFalse(model.confirmed)
        } finally { Dispatchers.resetMain() }
    }
    @Test fun oldEntryCannotOverwriteReopenedSamePhoto() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        val gate=CompletableDeferred<Unit>()
        try {
            var calls=0
            val model=PhotoAnalysisViewModel {
                val call=++calls
                if(call==1) withContext(NonCancellable) {gate.await()}
                PhotoAnalysis(listOf(Ingredient("result-$call")),listOf(it))
            }
            model.startEntry("photo","first");model.cancel()
            model.startEntry("photo","second");gate.complete(Unit);advanceUntilIdle()
            assertEquals("result-2",model.editor.ingredients.single().name)
        } finally {gate.complete(Unit);advanceUntilIdle();Dispatchers.resetMain()}
    }
}
