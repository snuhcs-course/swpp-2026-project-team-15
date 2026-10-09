package com.example.mylittlechef.navigation

import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavType

import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import com.example.mylittlechef.model.Preset
import com.example.mylittlechef.ui.fridge.add.AnalyzeScreen
import com.example.mylittlechef.ui.fridge.add.CaptureScreen
import com.example.mylittlechef.ui.fridge.add.ManualAddScreen

import com.example.mylittlechef.ui.onboarding.OnboardingScreen
import com.example.mylittlechef.ui.profile.EditAllergyScreen
import com.example.mylittlechef.ui.profile.EditNicknameScreen
import com.example.mylittlechef.ui.profile.EditUtensilScreen
import com.example.mylittlechef.ui.recipe.RecipeDetailScreen
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.UserViewModel

private const val START_DESTINATION = Routes.ONBOARDING

@Composable
fun AppNavHost(
    modifier: Modifier = Modifier
)
{
    val navController = rememberNavController()
    val user: UserViewModel = viewModel()
    val fridge: FridgeViewModel = viewModel()

    NavHost(
        navController = navController,
        startDestination = START_DESTINATION,
        modifier = modifier,
        enterTransition = { EnterTransition.None },
        exitTransition = { ExitTransition.None }
    ) {
        composable(Routes.ONBOARDING) {
            OnboardingScreen(
                user = user,
                onFinish = {
                    navController.navigate(Routes.MAIN)
                }
            )
        }

        composable(Routes.MAIN) {
            MainScreen(
                user = user,
                fridge = fridge,
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

        composable(
            route = "${Routes.RECIPE_DETAIL}/{recipeId}"
        ) { backStackEntry ->

            val recipeId = backStackEntry.arguments
                ?.getString("recipeId")
                ?.toLongOrNull()

            val recipe = Preset.sampleRecipes.find {
                it.id == recipeId
            }

            if (recipe != null) {
                RecipeDetailScreen(
                    user = user,
                    recipe = recipe,
                    onBackClick = {
                        navController.popBackStack()
                    },
                    onLikeClick = {}
                )
            }
        }
    }
}