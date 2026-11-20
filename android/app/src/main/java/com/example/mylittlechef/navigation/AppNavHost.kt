// AI-generated initial navigation scaffold with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
// Backend data wiring added with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
// Codex-assisted changes (GPT-6.1 Sol), 2026-10-14; human review pending.
// Pantry edit route added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
// Ingredient catalog wiring added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
package com.example.mylittlechef.navigation

import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.navigation.compose.currentBackStackEntryAsState
import com.example.mylittlechef.BuildConfig
import com.example.mylittlechef.data.local.PreferencesUsageDataSettings
import com.example.mylittlechef.data.remote.DishApiClient
import com.example.mylittlechef.data.telemetry.RemoteTelemetry
import com.example.mylittlechef.domain.Telemetry
import com.example.mylittlechef.domain.Usage
import com.example.mylittlechef.domain.UsageEvent
import com.example.mylittlechef.ui.profile.UsageDataNotice
import com.example.mylittlechef.viewmodel.UsageDataViewModel
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType

import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.example.mylittlechef.ui.fridge.add.AnalyzeScreen
import com.example.mylittlechef.ui.fridge.add.CaptureScreen
import com.example.mylittlechef.ui.fridge.add.ManualAddScreen

import com.example.mylittlechef.ui.onboarding.OnboardingScreen
import com.example.mylittlechef.ui.profile.EditAllergyScreen
import com.example.mylittlechef.ui.profile.EditPantryScreen
import com.example.mylittlechef.ui.profile.EditNicknameScreen
import com.example.mylittlechef.ui.profile.EditUtensilScreen
import com.example.mylittlechef.data.local.PreferencesAppDataReset
import com.example.mylittlechef.data.local.PreferencesFridgeRepository
import com.example.mylittlechef.data.local.IngredientPresentationProvider
import com.example.mylittlechef.data.local.PreferencesUserRepository
import com.example.mylittlechef.data.local.localDataStore
import com.example.mylittlechef.viewmodel.DataResetViewModel
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.IngredientCatalogViewModel
import com.example.mylittlechef.viewmodel.IngredientSuggestionViewModel
import com.example.mylittlechef.viewmodel.UserViewModel

@Composable
fun AppNavHost(
    modifier: Modifier = Modifier
)
{
    val navController = rememberNavController()
    val store = LocalContext.current.applicationContext.localDataStore
    val userRepository = remember(store) { PreferencesUserRepository(store) }
    val fridgeRepository = remember(store) { PreferencesFridgeRepository(store) }
    // Usage data for the beta week: one Telemetry for the whole app, handed to the ViewModels that emit events.
    val usageSettings = remember(store) { PreferencesUsageDataSettings(store) }
    val telemetryScope = rememberCoroutineScope()
    val telemetry: Telemetry = remember(usageSettings) {
        RemoteTelemetry(DishApiClient.telemetryApi::send, usageSettings, telemetryScope, BuildConfig.VERSION_NAME)
    }
    val usageFactory = remember(usageSettings) {
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = UsageDataViewModel(usageSettings) as T
        }
    }
    val usageData: UsageDataViewModel = viewModel(factory = usageFactory)
    SessionEvents(telemetry)
    val userFactory = remember(userRepository) {
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T =
                UserViewModel(repository = userRepository) as T
        }
    }
    val fridgeFactory = remember(fridgeRepository) {
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T =
                FridgeViewModel(repository = fridgeRepository, telemetry = telemetry) as T
        }
    }
    val user: UserViewModel = viewModel(factory = userFactory)
    val fridge: FridgeViewModel = viewModel(factory = fridgeFactory)
    val applicationContext = LocalContext.current.applicationContext
    val ingredientSuggestions: IngredientSuggestionViewModel = viewModel()
    val ingredientCatalog: IngredientCatalogViewModel = viewModel()
    val dataResetFactory = remember(store, applicationContext) {
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T =
                DataResetViewModel(PreferencesAppDataReset(store, applicationContext.cacheDir)) as T
        }
    }
    val dataReset: DataResetViewModel = viewModel(factory = dataResetFactory)

    // Wait for persisted data before choosing the first screen or fetching recommendations.
    if (!user.isLoaded || !fridge.isLoaded) return
    val startDestination = remember { if (user.onboardingComplete) Routes.MAIN else Routes.ONBOARDING }
    UsageDataNotice(usageData)
    val topEntry by navController.currentBackStackEntryAsState()
    val topRoute = topEntry?.destination?.route
    LaunchedEffect(topRoute) {
        val screen = when (topRoute) {
            Routes.ONBOARDING -> "onboarding"
            Routes.CAPTURE -> "capture"
            Routes.ANALYZE -> "analyze"
            Routes.MANUAL_ADD -> "manual_add"
            else -> null // the main screen reports its own tabs
        }
        if (screen != null) telemetry.track(Usage(UsageEvent.SCREEN_VIEW, screen = screen))
    }

    NavHost(
        navController = navController,
        startDestination = startDestination,
        modifier = modifier,
        enterTransition = { EnterTransition.None },
        exitTransition = { ExitTransition.None }
    ) {
        composable(Routes.ONBOARDING) {
            OnboardingScreen(
                user = user,
                fridge = fridge,
                onFinish = {
                    user.completeOnboarding()
                    navController.navigate(Routes.MAIN) {
                        popUpTo(Routes.ONBOARDING) { inclusive = true }
                    }
                }
            )
        }

        composable(Routes.MAIN) {
            MainScreen(
                user = user,
                fridge = fridge,
                ingredientSuggestions = ingredientSuggestions,
                dataReset = dataReset,
                telemetry = telemetry,
                usageData = usageData,
                onDataResetDone = {
                    // Like a fresh install: the first screen again, and Back cannot return to the old data.
                    navController.navigate(Routes.ONBOARDING) {
                        popUpTo(navController.graph.findStartDestination().id) { inclusive = true }
                        launchSingleTop = true
                    }
                },
                onAddIngredientClick = {
                    navController.navigate(Routes.CAPTURE)
                },
                onEditNicknameClick = {
                    navController.navigate(Routes.EDIT_NICKNAME)
                },
                onEditUtensilClick = {
                    navController.navigate(Routes.EDIT_UTENSIL)
                },
                onEditAllergyClick = {
                    navController.navigate(Routes.EDIT_ALLERGY)
                },
                onEditPantryClick = {
                    navController.navigate(Routes.EDIT_PANTRY)
                }
            )
        }

        composable(Routes.CAPTURE) {
            CaptureScreen(
                onBackClick = {
                    navController.popBackStack()
                },
                onCaptured = {
                    uri -> navController.navigate(Routes.analyzeRoute(uri.toString()))
                },
                onManualAddClick = {
                    navController.navigate(Routes.MANUAL_ADD)
                }
            )
        }

        composable(
            route = Routes.ANALYZE,
            arguments = listOf(
                navArgument(Routes.ARG_IMAGE_URI) {
                    type = NavType.StringType
                    nullable = true
                    defaultValue = null
                }
            )
        ) { backStackEntry ->
            AnalyzeScreen(
                fridge = fridge,
                ingredientCatalog = ingredientCatalog,
                imageUri = backStackEntry.arguments?.getString(Routes.ARG_IMAGE_URI),
                onBackClick = { navController.popBackStack() },
                onManualClick = {
                    navController.navigate(Routes.MANUAL_ADD) {
                        popUpTo(Routes.ANALYZE) { inclusive = true }
                    }
                },
                onRetakeClick = { navController.popBackStack() },
                onSaveClick = {
                    navController.popBackStack(Routes.MAIN, inclusive = false)
                }
            )
        }

        composable(Routes.MANUAL_ADD) {
            ManualAddScreen(
                fridge = fridge,
                ingredientCatalog = ingredientCatalog,
                onBackClick = {
                    navController.popBackStack()
                },
                onSaveClick = {
                    navController.popBackStack()
                    navController.popBackStack()
                }
            )
        }

        composable(Routes.EDIT_NICKNAME) {
            EditNicknameScreen(
                user = user,
                onBackClick = {
                    navController.popBackStack()
                },
                onSaveClick = {
                    navController.popBackStack()
                }
            )
        }

        composable(Routes.EDIT_UTENSIL) {
            EditUtensilScreen(
                user = user,
                onBackClick = {
                    navController.popBackStack()
                },
                onSaveClick = {
                    navController.popBackStack()
                }
            )
        }

        composable(Routes.EDIT_ALLERGY) {
            EditAllergyScreen(
                user = user,
                onBackClick = {
                    navController.popBackStack()
                },
                onSaveClick = {
                    navController.popBackStack()
                }
            )
        }

        composable(Routes.EDIT_PANTRY) {
            EditPantryScreen(
                fridge = fridge,
                onBackClick = { navController.popBackStack() },
                onSaveClick = { navController.popBackStack() }
            )
        }
    }
}

/** A session is the time the app is in the foreground; its events are sent when it goes to the background. */
@Composable
private fun SessionEvents(telemetry: Telemetry) {
    val owner = LocalLifecycleOwner.current
    DisposableEffect(owner, telemetry) {
        var started = 0L
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> {
                    started = System.currentTimeMillis()
                    telemetry.track(Usage(UsageEvent.SESSION_START))
                }
                Lifecycle.Event.ON_STOP -> {
                    val length = if (started > 0) System.currentTimeMillis() - started else null
                    telemetry.track(Usage(UsageEvent.SESSION_END, durationMs = length))
                    telemetry.flush()
                }
                else -> Unit
            }
        }
        owner.lifecycle.addObserver(observer)
        onDispose { owner.lifecycle.removeObserver(observer) }
    }
}
