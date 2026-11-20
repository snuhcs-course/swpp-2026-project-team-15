// AI-assisted selected-recipe UI regressions, 2026-11-10; human review pending.
package com.example.mylittlechef.ui.recipe

import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.unit.Density
import androidx.compose.ui.test.*
import androidx.compose.ui.test.junit4.createComposeRule
import com.example.mylittlechef.data.remote.RevisionChangeDto
import com.example.mylittlechef.model.*
import com.example.mylittlechef.viewmodel.*
import org.junit.Assert.*
import org.junit.Rule
import org.junit.Test

class HeSelectedRecipeUiTest {
    @get:Rule val rule=createComposeRule()
    private val recipe=Recipe(7,"두부 요리",10,2,listOf(Ingredient("두부")),listOf("원본 단계"),ingredientQuantities=listOf("2개"))
    @Test fun darkLargeTextKeepsProgressAndCancelReachable() {
        val user=UserViewModel(); var cancelled=0
        val state=SelectedRevisionState(RevisionStatus.LOADING,original=recipe)
        rule.setContent { CompositionLocalProvider(LocalDensity provides Density(LocalDensity.current.density,1.7f)) {
            com.example.mylittlechef.ui.theme.MyLittleChefTheme(darkTheme=true,dynamicColor=false) {
                RecipeDetailScreen(user,recipe,{}, {},onRequestRevision={},selectedState=state,onCancelRevision={cancelled++})
            }
        } }
        rule.onNodeWithTag("selected-revision-progress").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("요청 취소").performScrollTo().performClick()
        rule.runOnIdle { assertEquals(1,cancelled) }
    }
    @Test fun loadingShowsVisibleProgressAndCancellation() {
        val user=UserViewModel(); var cancelled=0
        val state=SelectedRevisionState(RevisionStatus.LOADING,original=recipe,mode="mock")
        rule.setContent { MaterialTheme { RecipeDetailScreen(user,recipe,{}, {},onRequestRevision={},
            selectedState=state,onCancelRevision={cancelled++}) } }
        rule.onNodeWithTag("selected-revision-progress").performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("요청 취소").performScrollTo().performClick()
        rule.runOnIdle { assertEquals(1,cancelled) }
    }
    @Test fun failuresKeepOriginalAndExposeRetryAndIngredientReview() {
        val user=UserViewModel(); var retries=0; var reviews=0
        val state=SelectedRevisionState(RevisionStatus.ERROR,original=recipe,problem=SelectedProblem.NETWORK,message="연결을 확인해 주세요")
        rule.setContent { MaterialTheme { RecipeDetailScreen(user,recipe,{}, {},onRequestRevision={retries++},
            selectedState=state,onReviewIngredients={reviews++}) } }
        rule.onNodeWithText("다시 시도").performScrollTo().performClick()
        rule.onNodeWithText("재료 확인").performScrollTo().performClick()
        rule.onNodeWithText("원본 단계",substring=true).performScrollTo().assertIsDisplayed()
        rule.runOnIdle { assertEquals(1,retries); assertEquals(1,reviews) }
    }
    @Test fun cachedSuggestionCanBeComparedWithoutAnotherRequest() {
        val user=UserViewModel(); var requests=0
        val state=SelectedRevisionState(RevisionStatus.REVISED,original=recipe,
            suggestion=recipe.copy(name="AI 두부 요리",ingredientQuantities=listOf("1개"),steps=listOf("수정 단계")),
            message="양 조절",changes=listOf(RevisionChangeDto("quantity","두부 양 조절")))
        rule.setContent { MaterialTheme { RecipeDetailScreen(user,recipe,{}, {},onRequestRevision={requests++},selectedState=state) } }
        rule.onNodeWithText("AI 제안 보기").performScrollTo().performClick()
        rule.onNodeWithText("수정 단계",substring=true).performScrollTo().assertIsDisplayed()
        rule.onNodeWithText("원본 보기").performScrollTo().performClick()
        rule.onNodeWithText("원본 단계",substring=true).performScrollTo().assertIsDisplayed()
        rule.runOnIdle { assertEquals(0,requests) }
    }
    @Test fun unregisteredIngredientsNeedASeparateConfirmation() {
        val user=UserViewModel(); var omissions=0
        val state=SelectedRevisionState(RevisionStatus.ERROR,original=recipe,problem=SelectedProblem.UNREGISTERED,
            unknownNames=listOf("미등록 재료"),message="이름을 확인해 주세요")
        rule.setContent { MaterialTheme { RecipeDetailScreen(user,recipe,{}, {},onRequestRevision={},selectedState=state,onIgnoreUnknown={omissions++}) } }
        rule.onNodeWithText("미등록 재료 제외하기").performScrollTo().performClick()
        rule.onNodeWithText("취소").performClick()
        rule.runOnIdle { assertEquals(0,omissions) }
        rule.onNodeWithText("미등록 재료 제외하기").performScrollTo().performClick()
        rule.onNodeWithText("이 재료 없이 요청").performClick()
        rule.runOnIdle { assertEquals(1,omissions) }
    }
}
