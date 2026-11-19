// AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.local.UserRepository
import com.example.mylittlechef.domain.UserProfile
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.UnconfinedTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.Assert.assertEquals
import org.junit.Test

/** Kept out of LocalViewModelsTest, a contributor test whose content CI pins by hash. */
@OptIn(ExperimentalCoroutinesApi::class)
class NicknameFallbackTest {
    private class FakeUsers : UserRepository {
        override val profile = MutableStateFlow(UserProfile())
        override suspend fun update(transform: (UserProfile) -> UserProfile) { profile.value = transform(profile.value) }
    }

    // Phone check (2026-11-19): a blank name showed as "님의 냉장고".
    @Test fun blankNicknameFallsBackToDefault() = runTest {
        Dispatchers.setMain(UnconfinedTestDispatcher(testScheduler))
        try {
            val repo = FakeUsers()
            val vm = UserViewModel(repository = repo)
            vm.updateNickname("   ")
            advanceUntilIdle()
            assertEquals(UserViewModel.DEFAULT_NICKNAME, vm.nickname)
            assertEquals(UserViewModel.DEFAULT_NICKNAME, repo.profile.value.nickname)
        } finally {
            Dispatchers.resetMain()
        }
    }
}
