package com.example.mylittlechef.navigation

import android.net.Uri

object Routes {
    const val ONBOARDING = "onboarding"
    const val MAIN = "main"

    const val FRIDGE = "fridge"
    const val RECIPE = "recipe"
    const val PROFILE = "profile"

    const val CAPTURE = "capture" // 재료 촬영
    const val ARG_IMAGE_URI = "imageUri"
    const val ANALYZE = "analyze?imageUri={imageUri}" // NavHost에 등록할 때 쓰는 패턴
    const val MANUAL_ADD = "manual_add" // 직접 입력

    const val EDIT_NICKNAME = "edit_nickname"
    const val EDIT_UTENSIL = "edit_utensil"
    const val EDIT_ALLERGY = "edit_allergy"

    const val RECIPE_DETAIL = "recipe_detail" // TODO: recipe 하위 route가 되어야 함

    fun analyzeRoute(imageUri: String) = "analyze?imageUri=${Uri.encode(imageUri)}"
}