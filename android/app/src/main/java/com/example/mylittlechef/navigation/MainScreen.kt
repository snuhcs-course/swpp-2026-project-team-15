// UAT stage 4 assisted by Codex, 2026-11-24; human review pending.
// UAT stage 1 assisted by Codex, 2026-11-24; human review pending.
// UX2 layout/lifecycle changes assisted by Codex, 2026-11-19; human review pending.
// Photo UI navigation motion assisted by Codex, 2026-11-19; human review pending.
// UI ergonomics and theme changes assisted by Codex, 2026-11-03; human review pending.
// AI-generated initial navigation scaffold with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
// Backend data wiring added with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
// Pantry edit navigation added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
// Merged with Claude Code (Opus 5.5), 2026-11-20: the recipe tab shows dishes from the YouTube-based
// server; usage data (screen views), data reset and the usage switch are wired underneath this UI.
package com.example.mylittlechef.navigation

import androidx.annotation.DrawableRes
import androidx.activity.compose.BackHandler
import androidx.compose.animation.Crossfade
import androidx.compose.animation.ExperimentalAnimationApi
import androidx.compose.animation.core.tween
import androidx.compose.animation.core.updateTransition
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.mylittlechef.R
import com.example.mylittlechef.data.local.localDataStore
import com.example.mylittlechef.data.local.SectionTourRepository
import com.example.mylittlechef.domain.*
import com.example.mylittlechef.ui.components.NavTabText
import com.example.mylittlechef.ui.fridge.*
import com.example.mylittlechef.ui.help.SectionTourHost
import com.example.mylittlechef.ui.profile.ProfileScreen
import com.example.mylittlechef.ui.recipe.RecipeScreen
import com.example.mylittlechef.ui.theme.GreenGray
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.viewmodel.*

// 하단 탭 정의. 탭을 추가/변경할 때 이 enum만 고치면 된다
// 아이콘은 단색 SVG(Vector Asset)여야 선택/비선택 색이 틴트로 바뀐다
enum class BottomTab(
    val route: String,
    val label: String,
    @DrawableRes val iconRes: Int
) {
    FRIDGE(Routes.FRIDGE, "냉장고", R.drawable.ic_fridge), // 아이콘 이름은 프로젝트에 맞게 수정
    RECIPE(Routes.RECIPE, "레시피", R.drawable.ic_recipe),
    PROFILE(Routes.PROFILE, "내 정보", R.drawable.ic_profile)
}

@OptIn(ExperimentalAnimationApi::class)
@Composable
fun MainScreen(
    user: UserViewModel,
    fridge: FridgeViewModel,
    onAddIngredientClick: () -> Unit,
    onEditNicknameClick: () -> Unit,
    onEditUtensilClick: () -> Unit,
    onEditAllergyClick: () -> Unit,
    modifier: Modifier = Modifier,
    ingredientSuggestions: IngredientSuggestionViewModel? = null,
    onEditPantryClick: () -> Unit = {},
    onManualAddClick: () -> Unit = onAddIngredientClick,
    dataReset: DataResetViewModel? = null,
    onDataResetDone: () -> Unit = {},
    telemetry: Telemetry = NoTelemetry,
    usageData: UsageDataViewModel? = null,
    dishViewModel: DishViewModel? = null,
    tourStore: SectionTourRepository? = null,
    onDishClick: (String) -> Unit = {}
) {
    // 요리 추천 탭의 상태. 탭을 오가거나 화면을 돌려도 유지되도록 이 화면 단위로 만든다
    val dishFactory = remember(telemetry) {
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = DishViewModel(telemetry = telemetry) as T
        }
    }
    // The app passes its own (the detail route reads the same one); previews and tests get their own here.
    val dishes: DishViewModel = dishViewModel ?: viewModel(factory = dishFactory)
    // The three peer tabs have no nested route stack. Keep each tab's saveable UI state
    // independently, while the parent AppNavHost still owns editing and detail navigation.
    var currentRoute by rememberSaveable {mutableStateOf(Routes.FRIDGE)}
    val tabStates=rememberSaveableStateHolder()
    val tabTransition=updateTransition(currentRoute,label="main-tabs")
    val tabReady=tabTransition.currentState==currentRoute && !tabTransition.isRunning
    BackHandler(enabled=currentRoute!=Routes.FRIDGE) {currentRoute=Routes.FRIDGE}
    val fridgeTransient=rememberFridgeTransientState()
    var previousRoute by rememberSaveable {mutableStateOf<String?>(null)}
    LaunchedEffect(currentRoute) {
        if(previousRoute==Routes.FRIDGE && currentRoute!=Routes.FRIDGE) fridgeTransient.reset()
        previousRoute=currentRoute
    }
    LaunchedEffect(currentRoute) {
        val screen = when (currentRoute) {
            Routes.FRIDGE -> "fridge"
            Routes.RECIPE -> "dishes"
            Routes.PROFILE -> "profile"
            else -> null
        }
        if (screen != null) telemetry.track(Usage(UsageEvent.SCREEN_VIEW, screen = screen))
    }

    val store=LocalContext.current.applicationContext.localDataStore
    val tourRepository=tourStore ?: remember(store) { SectionTourRepository(store) }
    SectionTourHost(tourRepository,currentRoute,automaticEnabled=user.onboardingComplete,
        navigationReady=tabReady,navigate={route -> currentRoute=route}) {
    Scaffold(
        modifier = modifier,
        snackbarHost = {if(currentRoute!=Routes.FRIDGE) AdditionFeedback(fridge,Modifier.padding(12.dp))},
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.background) {
                BottomTab.entries.forEach { tab ->
                    NavigationBarItem(
                        selected = currentRoute == tab.route,
                        onClick = {currentRoute=tab.route},
                        icon = {
                            Icon(
                                painter = painterResource(tab.iconRes),
                                contentDescription = tab.label
                            )
                        },
                        label = {
                            NavTabText(
                                text = tab.label
                            )
                        },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = MaterialTheme.colorScheme.onPrimaryContainer, // readable on the pill in dark mode
                            selectedTextColor = DeepGreen,
                            unselectedIconColor = GreenGray,
                            unselectedTextColor = GreenGray,
                            indicatorColor = MaterialTheme.colorScheme.primaryContainer // Figma처럼 선택 배경(알약 모양) 제거
                        )
                    )
                }
            }
        }
    ) { innerPadding ->
        tabTransition.Crossfade(modifier=Modifier.padding(innerPadding),animationSpec=tween(130)) {route ->
            tabStates.SaveableStateProvider(route) {
                when(route) {
                    Routes.FRIDGE -> FridgeScreen(user=user,fridge=fridge,
                        ingredientSuggestions=ingredientSuggestions,onAddIngredientClick=onAddIngredientClick,
                        onManualAddClick=onManualAddClick,transient=fridgeTransient,
                        dishes=dishes,onRecipeClick=onDishClick)
                    Routes.RECIPE -> RecipeScreen(fridge=fridge,dishes=dishes,
                        onDishClick={onDishClick(it.id)},active=currentRoute==Routes.RECIPE)
                    Routes.PROFILE -> ProfileScreen(user=user,fridge=fridge,
                        onEditNicknameClick=onEditNicknameClick,onEditUtensilClick=onEditUtensilClick,
                        onEditAllergyClick=onEditAllergyClick,onEditPantryClick=onEditPantryClick,
                        dataReset=dataReset,usageData=usageData,
                        onDataResetDone={dishes.resetState();onDataResetDone()})
                }
            }
        }
    }
    }
}
