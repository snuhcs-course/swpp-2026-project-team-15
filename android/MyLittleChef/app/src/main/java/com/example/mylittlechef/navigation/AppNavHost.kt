package com.example.mylittlechef.navigation

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier

import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController

import com.example.mylittlechef.ui.onboarding.OnboardingScreen

private const val START_DESTINATION = Routes.MAIN

@Composable
fun AppNavHost(
    modifier: Modifier = Modifier
)
{
    val navController = rememberNavController()

    NavHost(
        navController = navController,
        startDestination = START_DESTINATION,
        modifier = modifier
    ) {
        // TODO: Onboarding.kt

        composable(Routes.MAIN) {
            MainScreen(
                onAddIngredientClick = {
                    navController.navigate(Routes.CAPTURE)
                }
            )
        }

        composable(Routes.CAPTURE) {

        }

        composable(Routes.ANALYZE) {

        }

        composable(Routes.MANUAL_ADD) {

        }
    }
}