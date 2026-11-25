// Refresh state tests assisted by Codex, 2026-11-24.
package com.example.mylittlechef.dish
import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.viewmodel.*
import com.example.mylittlechef.domain.*
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.Assert.*
import org.junit.Test
@OptIn(ExperimentalCoroutinesApi::class)
class UatDishRefreshTest {
 private class Fake:DishApi {
  var calls=0;var fail=false;var count=20;var gate:CompletableDeferred<Unit>?=null
  var received=emptyList<String>()
  override suspend fun dishes()=DishCatalogResponse(emptyList(),0)
  override suspend fun videos(request:DishVideosRequest)=DishVideosResponse(emptyList())
  override suspend fun suggest(request:DishSuggestRequest):DishSuggestResponse {
   calls++;received=request.ingredients;gate?.await()
   if(fail) throw java.io.IOException("offline")
   return DishSuggestResponse("mock",(1..count).map {DishDto("$it","요리$it","",listOf("두부"),if(it%2==0) emptyList() else listOf("밥"),"",emptyList(),null)})
  }
 }
 @Test fun refreshChangesBatchAndIngredientSearchUsesAllCandidates()=runTest {
  Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
  try {
   val api=Fake();val vm=DishViewModel(api,0)
   vm.onFridgeChanged(listOf("두부","계란"));advanceUntilIdle()
   val first=vm.visibleSuggestions("").map {it.id}
   assertEquals(8,first.size);assertEquals(20,vm.relatedToIngredient("두부").size)
   assertEquals(20,(vm.state as DishUiState.Success).dishes.size)
   assertNotNull(vm.dishById("19"));assertEquals(20,vm.visibleSuggestions("요리").size)
   vm.selectSort(DishSort.NAME)
   vm.refreshSuggestions();advanceUntilIdle()
   val second=vm.visibleSuggestions("").map {it.id}
   assertTrue(first.toSet()!=second.toSet());assertTrue(second.none {it in first})
   assertTrue(vm.refreshFeedback!!.changed);assertEquals(1L,vm.refreshVersion)
   assertEquals(DishSort.NAME,vm.sort);assertEquals(listOf("두부","계란"),api.received)
   assertEquals(2,api.calls)
  } finally {Dispatchers.resetMain()}
 }
 @Test fun inflightDeduplicatesAndFailureRetainsListAndHiddenUndo()=runTest {
  Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
  val api=Fake()
  try {
   val vm=DishViewModel(api,0);vm.onFridgeChanged(listOf("두부"));advanceUntilIdle()
   val hidden=vm.visibleSuggestions("").first().id;vm.hide(hidden)
   val before=vm.visibleSuggestions("").map {it.id}
   api.gate=CompletableDeferred();api.fail=true
   vm.refreshSuggestions();vm.refreshSuggestions()
   assertEquals(2,api.calls);assertEquals(before,vm.visibleSuggestions("").map {it.id})
   api.gate!!.complete(Unit);advanceUntilIdle()
   assertTrue(vm.state is DishUiState.Error);assertEquals(hidden,vm.lastHidden)
   assertEquals(before,vm.visibleSuggestions("").map {it.id})
   vm.undoHide();assertTrue(vm.visibleSuggestions("").any {it.id==hidden})
   api.fail=false;vm.retry();advanceUntilIdle()
   assertTrue(vm.state is DishUiState.Success);assertTrue(vm.refreshFeedback!!.changed)
   assertEquals(3,api.calls)
  } finally {api.gate?.complete(Unit);Dispatchers.resetMain()}
 }
 @Test fun recommendationRefreshDoesNotStrandAnInFlightVideoLookup()=runTest {
  Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
  val videoGate=CompletableDeferred<Unit>()
  try {
   val api=object:DishApi {
    override suspend fun dishes()=DishCatalogResponse(emptyList(),0)
    override suspend fun suggest(request:DishSuggestRequest)=DishSuggestResponse("mock",listOf(DishDto("one","두부요리","",listOf("두부"),emptyList(),"",emptyList(),null)))
    override suspend fun videos(request:DishVideosRequest):DishVideosResponse {videoGate.await();return DishVideosResponse(emptyList())}
   }
   val vm=DishViewModel(api,0);vm.onFridgeChanged(listOf("두부"));advanceUntilIdle()
   vm.requestVideos(vm.dishById("one")!!)
   assertTrue(vm.videoState("one") is VideoUiState.Loading)
   vm.refreshSuggestions();advanceUntilIdle();videoGate.complete(Unit);advanceUntilIdle()
   assertTrue(vm.videoState("one") is VideoUiState.Success)
   vm.resetState();assertNull(vm.videoState("one"))
  } finally {videoGate.complete(Unit);Dispatchers.resetMain()}
 }
 @Test fun smallPoolReportsUnchangedAndInventoryInvalidatesOldResults()=runTest {
  Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
  val api=Fake().apply {count=3}
  try {
   val vm=DishViewModel(api,0);vm.onFridgeChanged(listOf("두부"));advanceUntilIdle()
   vm.refreshSuggestions();advanceUntilIdle();assertFalse(vm.refreshFeedback!!.changed)
   api.gate=CompletableDeferred();vm.onFridgeChanged(listOf("계란"))
   assertTrue(vm.relatedToIngredient("두부").isEmpty());assertTrue(vm.visibleSuggestions("").isEmpty())
   vm.onFridgeChanged(emptyList());api.gate!!.complete(Unit);advanceUntilIdle()
   assertTrue(vm.state is DishUiState.EmptyFridge);assertTrue(vm.visibleSuggestions("").isEmpty())
  } finally {api.gate?.complete(Unit);Dispatchers.resetMain()}
 }
}
