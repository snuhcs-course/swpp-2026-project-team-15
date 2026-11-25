// UAT stage 3 tests assisted by Codex, 2026-11-24.
package com.example.mylittlechef.dish
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.viewmodel.*
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test
@OptIn(ExperimentalCoroutinesApi::class)
class UatLoadingListTest {
 @Test fun refreshAndFailureKeepPreviousListWithoutDuplicateRequests()=runTest {
  Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
  var calls=0;val gate=CompletableDeferred<Unit>()
  val api=object:DishApi {
   override suspend fun dishes()=DishCatalogResponse(emptyList(),0)
   override suspend fun videos(request:DishVideosRequest)=DishVideosResponse(emptyList())
   override suspend fun suggest(request:DishSuggestRequest):DishSuggestResponse {
    calls++;if(calls>1){gate.await();throw java.io.IOException("network")}
    return DishSuggestResponse("mock",listOf(DishDto("rice","계란밥","밥",listOf("계란"),emptyList(),"",emptyList(),null)))
   }
  }
  try {
   val vm=DishViewModel(api,debounceMillis=0)
   vm.onFridgeChanged(listOf("계란"));advanceUntilIdle()
   vm.retry();assertTrue(vm.state is DishUiState.Loading)
   assertEquals("계란밥",vm.visibleSuggestions("").single().name)
   vm.onFridgeChanged(listOf("계란"));assertEquals(2,calls)
   gate.complete(Unit);advanceUntilIdle()
   assertTrue(vm.state is DishUiState.Error);assertTrue(vm.showingPreviousSuggestions)
   assertEquals(1,vm.visibleSuggestions("").size)
   vm.onFridgeChanged(emptyList());assertTrue(vm.visibleSuggestions("").isEmpty())
  } finally {gate.complete(Unit);advanceUntilIdle();Dispatchers.resetMain()}
 }
}
