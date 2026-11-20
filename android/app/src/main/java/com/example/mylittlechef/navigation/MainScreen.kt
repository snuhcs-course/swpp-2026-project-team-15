// UX2 layout/lifecycle changes assisted by Codex, 2026-11-19; human review pending.
// Photo UI navigation motion assisted by Codex, 2026-11-19; human review pending.
// UI ergonomics and theme changes assisted by Codex, 2026-11-03; human review pending.
// AI-generated initial navigation scaffold with Claude chat (Sonnet 5.5), 2026-10-04; adapted and reviewed by Ahyoon Choi.
// Backend data wiring added with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
// Pantry edit navigation added with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
// Merged with Claude Code (Opus 5.5), 2026-11-20: the recipe tab shows dishes from the YouTube-based
// server; usage data (screen views), data reset and the usage switch are wired underneath this UI.
package com.example.mylittlechef.navigation

import androidx.annotation.DrawableRes // drawable 리소스 ID 파라미터 표시
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.core.tween
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.foundation.layout.padding // 안쪽 여백 (탭 바에 화면이 안 가려지게)
import androidx.compose.material3.Icon // 탭 아이콘
import androidx.compose.material3.MaterialTheme // 테마 색상/글자 스타일
import androidx.compose.material3.NavigationBar // 하단 탭 바 컨테이너
import androidx.compose.material3.NavigationBarItem // 탭 하나
import androidx.compose.material3.NavigationBarItemDefaults // 탭 색상 지정
import androidx.compose.material3.Scaffold // 본문 + 하단바 뼈대
import androidx.compose.material3.Text // 탭 이름 글자
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewmodel.compose.viewModel
import com.example.mylittlechef.domain.NoTelemetry
import com.example.mylittlechef.domain.Telemetry
import com.example.mylittlechef.domain.Usage
import com.example.mylittlechef.domain.UsageEvent
import com.example.mylittlechef.viewmodel.DataResetViewModel
import com.example.mylittlechef.viewmodel.DishViewModel
import com.example.mylittlechef.viewmodel.UsageDataViewModel
import androidx.compose.ui.platform.LocalContext
import com.example.mylittlechef.data.local.localDataStore
import com.example.mylittlechef.data.local.SectionTourRepository
import com.example.mylittlechef.ui.help.SectionTourHost
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue // `by` 문법으로 상태 읽기
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color // 투명색 (선택 표시 배경 제거)
import androidx.compose.ui.res.painterResource // drawable → 그릴 수 있는 형태
import androidx.navigation.NavGraph.Companion.findStartDestination // 탭 전환 시 시작 지점 찾기
import androidx.navigation.compose.NavHost // 화면 전환 컨테이너
import androidx.navigation.compose.composable // 경로에 화면 등록
import androidx.navigation.compose.currentBackStackEntryAsState // 현재 경로를 상태로 관찰
import androidx.navigation.compose.rememberNavController // 탭용 NavController 생성
import com.example.mylittlechef.R
import com.example.mylittlechef.ui.components.NavTabText
import com.example.mylittlechef.ui.fridge.FridgeScreen
import com.example.mylittlechef.ui.profile.ProfileScreen
import com.example.mylittlechef.ui.dish.DishScreen

import com.example.mylittlechef.ui.theme.GreenGray
import com.example.mylittlechef.ui.theme.DeepGreen
import com.example.mylittlechef.viewmodel.FridgeViewModel
import com.example.mylittlechef.viewmodel.IngredientSuggestionViewModel
import com.example.mylittlechef.viewmodel.UserViewModel

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
    usageData: UsageDataViewModel? = null
) {
    // 요리 추천 탭의 상태. 탭을 오가거나 화면을 돌려도 유지되도록 이 화면 단위로 만든다
    val dishFactory = remember(telemetry) {
        object : ViewModelProvider.Factory {
            @Suppress("UNCHECKED_CAST")
            override fun <T : ViewModel> create(modelClass: Class<T>): T = DishViewModel(telemetry = telemetry) as T
        }
    }
    val dishes: DishViewModel = viewModel(factory = dishFactory)
    // 탭 전환만 담당하는 NavController (최상위 NavController와 별개)
    val tabNavController = rememberNavController()
    // 현재 보고 있는 탭의 경로. 바뀔 때마다 탭 바가 다시 그려진다
    val backStackEntry by tabNavController.currentBackStackEntryAsState()
    val currentRoute = backStackEntry?.destination?.route
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
    val tourRepository=remember(store) { SectionTourRepository(store) }
    SectionTourHost(tourRepository,currentRoute,automaticEnabled=user.onboardingComplete,navigate={route ->
        tabNavController.navigate(route) {
            popUpTo(tabNavController.graph.findStartDestination().id) { saveState=true }
            launchSingleTop=true;restoreState=true
        }
    }) {
    Scaffold(
        modifier = modifier,
        bottomBar = {
            NavigationBar(containerColor = MaterialTheme.colorScheme.background) {
                BottomTab.entries.forEach { tab ->
                    NavigationBarItem(
                        selected = currentRoute == tab.route,
                        onClick = {
                            tabNavController.navigate(tab.route) {
                                popUpTo(tabNavController.graph.findStartDestination().id) {
                                    saveState = true // 떠나는 탭의 상태(스크롤 위치 등) 저장
                                }
                                launchSingleTop = true // 같은 탭을 또 눌러도 중복 생성 안 함
                                restoreState = true // 돌아오면 저장해 둔 상태 복원
                            }
                        },
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
                            selectedIconColor = DeepGreen,
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
        // 탭 3개를 전환하는 NavHost. 탭 바에 가려지지 않게 innerPadding 적용
        NavHost(
            navController = tabNavController,
            startDestination = Routes.FRIDGE,
            modifier = Modifier.padding(innerPadding),
            enterTransition = { fadeIn(tween(130)) },
            exitTransition = { fadeOut(tween(90)) }
        ) {
            composable(Routes.FRIDGE) {
                FridgeScreen(
                    user = user,
                    fridge = fridge,
                    ingredientSuggestions = ingredientSuggestions,
                    onAddIngredientClick = onAddIngredientClick,
                    onManualAddClick = onManualAddClick
                )
            }
            composable(Routes.RECIPE) {
                DishScreen(user = user, fridge = fridge, dishes = dishes)
            }
            composable(Routes.PROFILE) {
                ProfileScreen(
                    user = user,
                    fridge = fridge,
                    onEditNicknameClick = onEditNicknameClick,
                    onEditUtensilClick = onEditUtensilClick,
                    onEditAllergyClick = onEditAllergyClick,
                    onEditPantryClick = onEditPantryClick,
                    dataReset = dataReset,
                    usageData = usageData,
                    onDataResetDone = {
                        dishes.resetState()
                        onDataResetDone()
                    }
                )
            }
        }
    }
    }
}
 
