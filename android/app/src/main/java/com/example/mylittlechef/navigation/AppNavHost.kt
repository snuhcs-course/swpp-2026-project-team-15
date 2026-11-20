// UX2 layout/lifecycle changes assisted by Codex, 2026-11-19; human review pending.
// Photo UI navigation motion assisted by Codex, 2026-11-19; human review pending.
// HE ingredient/exploration changes assisted by Codex, 2026-11-10; human review pending.
// AI-generated initial navigation scaffold with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
// Backend data wiring added with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
// Codex-assisted changes (GPT-6.1 Sol), 2026-10-14; human review pending.
// Pantry edit route added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
// Ingredient catalog wiring added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
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
import com.example.mylittlechef.ui.profile.EditAllergyScreen
import com.example.mylittlechef.ui.profile.EditPantryScreen
import com.example.mylittlechef.ui.profile.EditNicknameScreen
import com.example.mylittlechef.ui.profile.EditUtensilScreen
import com.example.mylittlechef.ui.recipe.RecipeDetailScreen
import com.example.mylittlechef.data.local.PreferencesFridgeRepository
import com.example.mylittlechef.data.local.IngredientPresentationProvider
import com.example.mylittlechef.data.local.PreferencesUserRepository
import com.example.mylittlechef.data.local.localDataStore
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.IngredientCatalogViewModel
import com.example.mylittlechef.viewmodel.IngredientSuggestionViewModel
import com.example.mylittlechef.viewmodel.RecipeViewModel
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
                FridgeViewModel(repository = fridgeRepository) as T
        }
    }
    val user: UserViewModel = viewModel(factory = userFactory)
    val fridge: FridgeViewModel = viewModel(factory = fridgeFactory)
    val applicationContext = LocalContext.current.applicationContext
    val recipeFactory = remember(applicationContext) {
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T =
                RecipeViewModel(ingredientIds = IngredientPresentationProvider.get(applicationContext).ingredientIds) as T
        }
    }
    val recipes: RecipeViewModel = viewModel(factory = recipeFactory)
    val ingredientSuggestions: IngredientSuggestionViewModel = viewModel()
    val ingredientCatalog: IngredientCatalogViewModel = viewModel()

    // Wait for persisted data before choosing the first screen or fetching recommendations.
    if (!user.isLoaded || !fridge.isLoaded) return
    LaunchedEffect(fridge.ingredients, user.allergies, user.utensils) {
        recipes.updateUserContext(fridge.ingredients, user.allergies, user.utensils)
    }
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
                recipes = recipes,
                ingredientSuggestions = ingredientSuggestions,
                onAddIngredientClick = {
                    navController.navigate(Routes.CAPTURE)
                },
                onManualAddClick = { entrySheet="manual" },
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
                },
                onRecipeCardClick = {
                    recipe ->
                    navController.navigate("${Routes.RECIPE_DETAIL}/${recipe.id}")
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

        composable(
            route = "${Routes.RECIPE_DETAIL}/{recipeId}"
        ) { backStackEntry ->

            val recipeId = backStackEntry.arguments
                ?.getString("recipeId")
                ?.toLongOrNull()

            val recipe = recipes.find(recipeId)

            if (recipe != null) {
                RecipeDetailScreen(
                    user = user,
                    recipe = recipe,
                    onBackClick = {
                        navController.popBackStack()
                    },
                    onLikeClick = {},
                    revisionState = recipes.revisionState(recipe.id),
                    fridge = fridge,
                    selectedState = recipes.selectedRevisionState(recipe.id),
                    onCancelRevision = { recipes.cancelRevision(recipe.id) },
                    onReviewIngredients = {
                        navController.navigate(Routes.MAIN) { popUpTo(Routes.MAIN) { inclusive=true }; launchSingleTop=true }
                    },
                    onIgnoreUnknown = {
                        recipes.updateUserContext(fridge.ingredients,user.allergies,user.utensils)
                        recipes.requestRevision(recipe.id,ignoreUnknown=true)
                    },
                    onReloadRecipes = { recipes.search(recipes.searchQuery,fridge.ingredients);navController.popBackStack() },
                    batchRevision = recipes.supportsBatchRevision,
                    onRequestRevision = if (recipes.supportsRevision) ({
                        recipes.updateUserContext(fridge.ingredients, user.allergies, user.utensils)
                        recipes.requestRevision(recipe.id)
                    }) else null
                )
            }
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
