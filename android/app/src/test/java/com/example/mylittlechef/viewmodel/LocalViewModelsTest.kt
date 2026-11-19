package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.local.FridgeRepository
import com.example.mylittlechef.data.local.UserRepository
import com.example.mylittlechef.domain.FridgeInventory
import com.example.mylittlechef.domain.UserProfile
import com.example.mylittlechef.model.Ingredient
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

private class FakeFridgeRepository : FridgeRepository {
    override val names = MutableStateFlow<List<String>>(emptyList())
    override suspend fun add(values: List<String>) { names.value = FridgeInventory(names.value).addAll(values).names }
    override suspend fun remove(value: String) { names.value = FridgeInventory(names.value).remove(value).names }
}

private class FakeUserRepository : UserRepository {
    override val profile = MutableStateFlow(UserProfile())
    override suspend fun update(transform: (UserProfile) -> UserProfile) { profile.value = transform(profile.value) }
}

@OptIn(ExperimentalCoroutinesApi::class)
class LocalViewModelsTest {
    @Test fun fridge_addsToRepositoryAndUpdatesUi() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val repo = FakeFridgeRepository()
            val vm = FridgeViewModel(repo)
            assertTrue(vm.isLoaded)
            vm.addIngredients(listOf(Ingredient(" 두부 "), Ingredient("두부")))
            advanceUntilIdle()
            assertEquals(listOf(Ingredient("두부")), vm.ingredients)
            assertEquals(listOf("두부"), repo.names.value)
        } finally {
            Dispatchers.resetMain()
        }
    }

    @Test fun user_updatesProfileAndCompletesOnboarding() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val repo = FakeUserRepository()
            val vm = UserViewModel(repository = repo)
            assertTrue(vm.isLoaded)
            vm.updateNickname(" 수현 ")
            vm.updateUtensils(listOf("인덕션"))
            vm.updateAllergies(listOf("우유"))
            vm.addLikes(42)
            vm.completeOnboarding()
            advanceUntilIdle()
            assertEquals("수현", vm.nickname)
            assertEquals(listOf("인덕션"), vm.utensils)
            assertEquals(listOf("우유"), vm.allergies)
            assertEquals(listOf(42L), vm.likes)
            assertTrue(repo.profile.value.onboardingComplete)
        } finally {
            Dispatchers.resetMain()
        }
    }
}
