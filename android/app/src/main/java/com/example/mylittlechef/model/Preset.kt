// AI-assisted with Codex (GPT-6.1 Sol), 2026-10-17; human review pending.
package com.example.mylittlechef.model

object Preset {
    // Frequent recipe ingredients that are practical to confirm once during onboarding.
    val pantrySeasonings = listOf(
        "소금", "설탕", "간장", "식용유", "참기름", "후추",
        "다진마늘", "고춧가루", "깨소금", "식초", "고추장", "된장"
    )

    val pantryBasics = listOf(
        "양파", "대파", "당근", "계란", "밥", "두부", "감자", "김치"
    )

    val utensils = listOf(
        "가스레인지",
        "인덕션",
        "오븐",
        "에어프라이어",
        "믹서기",
        "전자레인지"
    )

    val allergies = listOf(
        "땅콩",
        "우유",
        "밀",
        "달걀",
        "견과류",
        "갑각류",
        "생선",
        "대두"
    )

    // TODO: add image
    val analyzeResult: List<Ingredient> = listOf(
        Ingredient("소금"),
        Ingredient("양파"),
        Ingredient("두부"),
        Ingredient("김치")
    )
}