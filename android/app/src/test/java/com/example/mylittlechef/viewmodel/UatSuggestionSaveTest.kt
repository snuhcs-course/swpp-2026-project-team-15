// UAT stage 1 tests assisted by Codex, 2026-11-24.
package com.example.mylittlechef.viewmodel
import com.example.mylittlechef.data.local.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test
import java.io.IOException
@OptIn(ExperimentalCoroutinesApi::class)
class UatSuggestionSaveTest {
 @Test fun saveIsDurableFirstFailureRetryAndUndoFailureRetry()=runTest {
  Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
  val gate=CompletableDeferred<Unit>();var fail=true;var failUndo=true;var writes=0
  val repo=object:FridgeRepository {
   override val names=MutableStateFlow(listOf("마늘"))
   override suspend fun add(values:List<String>) {names.value+=values}
   override suspend fun remove(value:String) {names.value-=value}
   override suspend fun addSuggested(name:String,token:String):AdditionResult {
    writes++;gate.await();if(fail)throw IOException("disk")
    names.value+=name;return AdditionResult.Added(AddedIngredient(name,token))
   }
   override suspend fun undoSuggested(receipt:AddedIngredient):Boolean {if(failUndo)throw IOException("disk");names.value-=receipt.name;return true}
  }
  try {
   val vm=FridgeViewModel(repo);vm.addSuggested("두부");vm.addSuggested("계란")
   assertTrue(vm.isSavingSuggestion);assertNull(vm.additionNotice);assertEquals(1,writes)
   assertEquals(listOf("마늘"),vm.ingredients.map {it.name})
   gate.complete(Unit);advanceUntilIdle();assertEquals(AdditionNoticeKind.ADD_ERROR,vm.additionNotice!!.kind)
   fail=false;vm.actOnAddition(vm.additionNotice!!.id);advanceUntilIdle()
   val success=vm.additionNotice!!;assertEquals(AdditionNoticeKind.ADDED,success.kind)
   vm.actOnAddition(success.id);advanceUntilIdle();assertEquals(AdditionNoticeKind.UNDO_ERROR,vm.additionNotice!!.kind)
   assertTrue("두부" in repo.names.value)
   failUndo=false;vm.actOnAddition(vm.additionNotice!!.id);advanceUntilIdle()
   assertEquals(AdditionNoticeKind.UNDONE,vm.additionNotice!!.kind);assertEquals(listOf("마늘"),repo.names.value)
   vm.actOnAddition(success.id);assertEquals(AdditionNoticeKind.UNDONE,vm.additionNotice!!.kind)
  } finally {gate.complete(Unit);advanceUntilIdle();Dispatchers.resetMain()}
 }
 @Test fun newestNoticeIsTheOnlyUndoAndDuplicateNeverDeletesOriginal()=runTest {
  Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
  try {
   val vm=FridgeViewModel();vm.addSuggested("마늘");val old=vm.additionNotice!!.id
   vm.addSuggested("계란");vm.actOnAddition(old)
   assertEquals(listOf("마늘","계란"),vm.ingredients.map {it.name})
   vm.addSuggested("마늘");assertEquals(AdditionNoticeKind.DUPLICATE,vm.additionNotice!!.kind)
   vm.actOnAddition(vm.additionNotice!!.id);assertEquals(2,vm.ingredients.size)
  } finally {Dispatchers.resetMain()}
 }
}
