// UX2 layout/lifecycle changes assisted by Codex, 2026-11-19; human review pending.
// Cooking-mode usage events (one call per site) added with Claude Code (Opus 5.5), 2026-11-26.
// Photo UI navigation motion assisted by Codex, 2026-11-19; human review pending.
// HE ingredient/exploration changes assisted by Codex, 2026-11-10; human review pending.
// AI-generated initial navigation scaffold with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
// Backend data wiring added with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
// Codex-assisted changes (GPT-6.1 Sol), 2026-10-14; human review pending.
// Pantry edit route added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
// Ingredient catalog wiring added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
// Merged with Claude Code (Opus 5.5), 2026-11-20: this navigation shell (#23/#24) with the YouTube-based
// dish data, usage data (sessions, screen views incl. the entry sheets), data reset and the usage notice.
package com.example.mylittlechef.navigation

import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.Composable
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.core.net.toUri
import com.example.mylittlechef.data.IngredientAnalyzer
import com.example.mylittlechef.viewmodel.PhotoAnalysisViewModel
import com.example.mylittlechef.ui.fridge.add.EntrySheet
import com.example.mylittlechef.ui.fridge.add.LocalEntrySheet
import java.util.UUID
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType

import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.compose.runtime.getValue
import com.example.mylittlechef.data.local.UsageGuideRepository
import com.example.mylittlechef.ui.help.FirstUseGuide
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.example.mylittlechef.ui.fridge.add.AnalyzeScreen
import com.example.mylittlechef.ui.fridge.add.CaptureScreen
import com.example.mylittlechef.ui.fridge.add.ManualAddScreen

import com.example.mylittlechef.ui.onboarding.OnboardingScreen
import com.example.mylittlechef.ui.profile.EditPantryScreen
import com.example.mylittlechef.ui.profile.EditNicknameScreen
import com.example.mylittlechef.data.local.PreferencesFridgeRepository
import com.example.mylittlechef.data.local.IngredientPresentationProvider
import com.example.mylittlechef.data.local.PreferencesUserRepository
import com.example.mylittlechef.data.local.localDataStore
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.IngredientCatalogViewModel
import com.example.mylittlechef.viewmodel.IngredientSuggestionViewModel
import com.example.mylittlechef.viewmodel.UserViewModel
import androidx.activity.compose.LocalActivity
import androidx.compose.runtime.DisposableEffect
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.navigation.NavGraph.Companion.findStartDestination
import com.example.mylittlechef.data.local.PreferencesAppDataReset
import com.example.mylittlechef.data.local.PreferencesUsageDataSettings
import com.example.mylittlechef.data.telemetry.AppUsage
import com.example.mylittlechef.domain.Telemetry
import com.example.mylittlechef.domain.Usage
import com.example.mylittlechef.domain.UsageEvent
import com.example.mylittlechef.ui.profile.UsageDataNotice
import com.example.mylittlechef.viewmodel.DataResetViewModel
import com.example.mylittlechef.viewmodel.UsageDataViewModel
import com.example.mylittlechef.data.local.PreferencesFavoriteDishes
import com.example.mylittlechef.ui.recipe.RecipeDetailScreen
import com.example.mylittlechef.viewmodel.DishViewModel

@Composable
fun AppNavHost(
    modifier: Modifier = Modifier
)
{
    val navController = rememberNavController()
    val store = LocalContext.current.applicationContext.localDataStore
    val userRepository = remember(store) { PreferencesUserRepository(store) }
    val fridgeRepository = remember(store) { PreferencesFridgeRepository(store) }
    // Usage data for the beta week: one Telemetry for the app process, handed to the ViewModels that emit events.
    val usageSettings = remember(store) { PreferencesUsageDataSettings(store) }
    val context = LocalContext.current
    val telemetry: Telemetry = remember { AppUsage.telemetry(context) }
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
    // The dish list and the detail route share one: the detail shows the dish the list holds.
    val dishFactory = remember(store, telemetry) {
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T =
                DishViewModel(telemetry = telemetry, favoriteStore = PreferencesFavoriteDishes(store)) as T
        }
    }
    val dishes: DishViewModel = viewModel(factory = dishFactory)

    // Wait for persisted data before choosing the first screen or fetching recommendations.
    if (!user.isLoaded || !fridge.isLoaded) return
    val startDestination = remember { if (user.onboardingComplete) Routes.MAIN else Routes.ONBOARDING }
    var entrySheet by rememberSaveable { mutableStateOf<String?>(null) }
    var photoUri by rememberSaveable { mutableStateOf<String?>(null) }
    var photoToken by rememberSaveable { mutableStateOf("") }
    val photoFactory = remember(applicationContext) { object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T: ViewModel> create(modelClass: Class<T>): T {
            val analyzer=IngredientAnalyzer(applicationContext)
            return PhotoAnalysisViewModel { analyzer.review(it.toUri()) } as T
        }
    } }
    val photoReview: PhotoAnalysisViewModel = viewModel(factory=photoFactory)
    fun closeEntry() { if(entrySheet=="photo") photoReview.cancel(); entrySheet=null }
    UsageDataNotice(usageData)
    val topEntry by navController.currentBackStackEntryAsState()
    val topRoute = topEntry?.destination?.route
    // Screen views: the full-screen routes and the entry sheets that open above the main screen.
    LaunchedEffect(topRoute, entrySheet) {
        val screen = when {
            entrySheet == "manual" -> "manual_add"
            entrySheet == "photo" -> "analyze"
            topRoute == Routes.ONBOARDING -> "onboarding"
            topRoute == Routes.CAPTURE -> "capture"
            topRoute == Routes.ANALYZE -> "analyze"
            topRoute == Routes.MANUAL_ADD -> "manual_add"
            else -> null // the main screen reports its own tabs
        }
        if (screen != null) telemetry.track(Usage(UsageEvent.SCREEN_VIEW, screen = screen))
    }


    NavHost(
        navController = navController,
        startDestination = startDestination,
        modifier = modifier,
        enterTransition = { fadeIn(tween(180)) + slideInHorizontally(tween(180)) { it / 20 } },
        exitTransition = { fadeOut(tween(100)) },
        popEnterTransition = { fadeIn(tween(140)) },
        popExitTransition = { fadeOut(tween(120)) + slideOutHorizontally(tween(140)) { it / 20 } }
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
                dishViewModel = dishes,
                onDishClick = { id -> navController.navigate(Routes.recipeDetailRoute(id)) },
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
                onManualAddClick = { entrySheet="manual" },
                onEditNicknameClick = {
                    navController.navigate(Routes.EDIT_NICKNAME)
                },
                onEditUtensilClick = {},
                onEditAllergyClick = {},
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
                    uri ->
                    photoUri=uri.toString(); photoToken=UUID.randomUUID().toString()
                    navController.popBackStack(Routes.MAIN, false); entrySheet="photo"
                },
                onManualAddClick = {
                    navController.popBackStack(Routes.MAIN, false); entrySheet="manual"
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
                    navController.popBackStack(Routes.MAIN, inclusive = false)
                }
            )
        }

        composable(
            route = "${Routes.RECIPE_DETAIL}/{${Routes.ARG_DISH_ID}}",
            arguments = listOf(navArgument(Routes.ARG_DISH_ID) { type = NavType.StringType })
        ) { entry ->
            val id = entry.arguments?.getString(Routes.ARG_DISH_ID).orEmpty()
            val dish = dishes.dishById(id)
            if (dish == null) {
                LaunchedEffect(id) { navController.popBackStack() }
                return@composable
            }
            DisposableEffect(id) {
                dishes.selectDish(id)
                onDispose { dishes.selectDish(null) }
            }
            LaunchedEffect(id) {
                dishes.requestVideos(dish)
                if (dish.hasRecipe) dishes.recipes.requestRecipe(id)
            }
            RecipeDetailScreen(
                dish = dish,
                liked = dishes.isFavorite(id),
                recipe = dishes.recipes.recipeState(id),
                revision = dishes.recipes.reviseState(id),
                videos = dishes.videoState(id),
                fridge = fridge,
                onBackClick = { navController.popBackStack() },
                onLikeClick = { dishes.toggleFavorite(dish) },
                onRetryRecipe = { dishes.recipes.requestRecipe(id) },
                onRevise = { dishes.recipes.requestRevision(id) },
                onRetryVideos = { dishes.requestVideos(dish) },
                onPlayerError = { dishes.onPlayerError(id) },
                cookingTracker = dishes
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

        // Old saved navigation entries must not reopen retired settings after an update.
        listOf(Routes.EDIT_UTENSIL,Routes.EDIT_ALLERGY).forEach { retired ->
            composable(retired) {
                LaunchedEffect(Unit) {
                    navController.navigate(Routes.MAIN) {
                        popUpTo(retired) {inclusive=true}
                        launchSingleTop=true
                    }
                }
            }
        }

        composable(Routes.EDIT_PANTRY) {
            EditPantryScreen(
                fridge = fridge,
                onBackClick = { navController.popBackStack() },
                onSaveClick = { navController.popBackStack() }
            )
        }

    }
    entrySheet?.let { kind ->
        key(kind, photoToken) {
            EntrySheet(onClose=::closeEntry,heightFraction=if(kind=="manual") .72f else .94f) {
                val controls=LocalEntrySheet.current
                if(kind=="manual") ManualAddScreen(fridge, ingredientCatalog,
                    onBackClick={controls?.requestClose?.invoke()}, onSaveClick={controls?.complete?.invoke()})
                else AnalyzeScreen(fridge=fridge, ingredientCatalog=ingredientCatalog,
                    imageUri=photoUri, reviewModel=photoReview, entryToken=photoToken,
                    onBackClick={controls?.requestClose?.invoke()},
                    onManualClick={photoReview.cancel();entrySheet="manual"},
                    onRetakeClick={closeEntry();navController.navigate(Routes.CAPTURE)},
                    onSaveClick={controls?.complete?.invoke()})
            }
        }
    }

}

/** A session is the time the app is in the foreground; its events are sent when it goes to the background. */
@Composable
private fun SessionEvents(telemetry: Telemetry) {
    val owner = LocalLifecycleOwner.current
    val activity = LocalActivity.current
    DisposableEffect(owner, telemetry) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_START -> AppUsage.sessions.onStart(telemetry)
                Lifecycle.Event.ON_STOP ->
                    AppUsage.sessions.onStop(telemetry, activity?.isChangingConfigurations == true)
                else -> Unit
            }
        }
        owner.lifecycle.addObserver(observer)
        onDispose { owner.lifecycle.removeObserver(observer) }
    }
}
