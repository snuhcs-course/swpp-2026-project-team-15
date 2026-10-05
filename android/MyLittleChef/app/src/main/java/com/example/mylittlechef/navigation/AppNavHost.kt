package com.example.mylittlechef.navigation

import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.lifecycle.viewmodel.compose.viewModel

import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController

import com.example.mylittlechef.ui.onboarding.OnboardingScreen
import com.example.mylittlechef.ui.profile.EditAllergyScreen
import com.example.mylittlechef.ui.profile.EditNicknameScreen
import com.example.mylittlechef.ui.profile.EditUtensilScreen
import com.example.mylittlechef.viewmodel.UserViewModel

private const val START_DESTINATION = Routes.MAIN

@Composable
fun AppNavHost(
    modifier: Modifier = Modifier
)
{
    val navController = rememberNavController()
    val user: UserViewModel = viewModel()

    NavHost(
        navController = navController,
        startDestination = START_DESTINATION,
        modifier = modifier,
        enterTransition = { EnterTransition.None },
        exitTransition = { ExitTransition.None }
    ) {
        // TODO: Onboarding.kt

        composable(Routes.MAIN) {
            MainScreen(
                user,
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
                }
            )
        }

        composable(Routes.CAPTURE) {

        }

        composable(Routes.ANALYZE) {

        }

        composable(Routes.MANUAL_ADD) {

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
    }
}