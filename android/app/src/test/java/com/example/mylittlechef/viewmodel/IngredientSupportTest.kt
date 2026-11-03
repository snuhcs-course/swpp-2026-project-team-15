package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.remote.*
import com.example.mylittlechef.model.Ingredient
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import okhttp3.MultipartBody
import org.junit.Assert.*
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class IngredientSupportTest {
    private abstract class FakeApi : IngredientSupportApi {
        override suspend fun ingredientNames() = IngredientCatalogResponse(emptyList())
        override suspend fun ingredientSuggestions(request: IngredientSuggestionRequest) = IngredientSuggestionResponse(emptyList())
        override suspend fun analyze(image: MultipartBody.Part): AnalyzeResponse = error("Not used")
        override suspend fun recommend(request: RecommendRequest): RecommendResponse = error("Not used")
    }

    @Test fun lateSuggestionResponseCannotReplaceNewInventory() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        val old = CompletableDeferred<Unit>()
        val api = object : FakeApi() {
            override suspend fun ingredientSuggestions(request: IngredientSuggestionRequest): IngredientSuggestionResponse {
                if (request.ingredients == listOf("두부")) withContext(NonCancellable) { old.await() }
                return IngredientSuggestionResponse(listOf(IngredientSuggestionDto(request.ingredients.single(), 1, 5, emptyList())))
            }
        }
        try {
            val vm = IngredientSuggestionViewModel(api)
            vm.refresh(listOf(Ingredient("두부")))
            vm.refresh(listOf(Ingredient("계란")))
            old.complete(Unit)
            advanceUntilIdle()
            assertEquals("계란", vm.suggestions.single().name)
            assertFalse(vm.isLoading)
            assertNull(vm.error)
        } finally { old.complete(Unit); Dispatchers.resetMain() }
    }

    @Test fun unavailableCatalogCanBeRetried() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        var calls = 0
        val api = object : FakeApi() {
            override suspend fun ingredientNames(): IngredientCatalogResponse {
                if (++calls == 1) error("Offline")
                return IngredientCatalogResponse(listOf("양파"))
            }
        }
        try {
            val vm = IngredientCatalogViewModel(api)
            vm.load(); advanceUntilIdle()
            assertTrue(vm.names.isEmpty())
            vm.load(); advanceUntilIdle()
            assertEquals(listOf("양파"), vm.names)
        } finally { Dispatchers.resetMain() }
    }
}
