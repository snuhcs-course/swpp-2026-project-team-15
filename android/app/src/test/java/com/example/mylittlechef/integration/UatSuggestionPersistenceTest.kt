// UAT stage 1 tests assisted by Codex, 2026-11-24.
package com.example.mylittlechef.integration
import androidx.datastore.preferences.core.PreferenceDataStoreFactory
import com.example.mylittlechef.data.local.*
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.first
import org.junit.Assert.*
import org.junit.Test
import java.nio.file.Files
class UatSuggestionPersistenceTest {
 @Test fun duplicateUndoAndReaddedNameAreTransactionSafe()=runBlocking {
  val file=Files.createTempDirectory("uat-suggestion").resolve("state.preferences_pb").toFile()
  val scope=CoroutineScope(Dispatchers.IO+SupervisorJob())
  try {
   val repo=PreferencesFridgeRepository(PreferenceDataStoreFactory.create(scope=scope,produceFile={file}))
   repo.add(listOf("마늘"))
   assertTrue(repo.addSuggested(" 마늘 ","duplicate") is AdditionResult.AlreadyOwned)
   val receipt=(repo.addSuggested("다진마늘","a") as AdditionResult.Added).receipt
   repo.add(listOf("계란"))
   assertTrue(repo.undoSuggested(receipt))
   assertEquals(listOf("마늘","계란"),repo.names.first())
   val old=(repo.addSuggested("두부","b") as AdditionResult.Added).receipt
   repo.remove("두부");repo.add(listOf("두부"))
   assertFalse(repo.undoSuggested(old))
   assertEquals(listOf("마늘","계란","두부"),repo.names.first())
  } finally {scope.cancel();scope.coroutineContext[Job]!!.join();file.delete();file.parentFile?.delete()}
 }
 @Test fun latestReceiptWorksAfterStoreReopen()=runBlocking {
  val file=Files.createTempDirectory("uat-reopen").resolve("state.preferences_pb").toFile()
  val first=CoroutineScope(Dispatchers.IO+SupervisorJob())
  val receipt:AddedIngredient
  try {val repo=PreferencesFridgeRepository(PreferenceDataStoreFactory.create(scope=first,produceFile={file}));receipt=(repo.addSuggested("양파","id") as AdditionResult.Added).receipt}
  finally {first.cancel();first.coroutineContext[Job]!!.join()}
  val second=CoroutineScope(Dispatchers.IO+SupervisorJob())
  try {val repo=PreferencesFridgeRepository(PreferenceDataStoreFactory.create(scope=second,produceFile={file}));assertTrue(repo.undoSuggested(receipt));assertTrue(repo.names.first().isEmpty())}
  finally {second.cancel();second.coroutineContext[Job]!!.join();file.delete();file.parentFile?.delete()}
 }
}
