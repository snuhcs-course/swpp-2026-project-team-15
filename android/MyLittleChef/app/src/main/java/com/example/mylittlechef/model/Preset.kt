package com.example.mylittlechef.model

object Preset {
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

    // TODO: add image
    val sampleRecipes: List<Recipe> = listOf(
        Recipe(
            id = 0,
            name = "두부김치",
            time = 15,
            serving = 1,
            ingredients = listOf(
                Ingredient("두부"),
                Ingredient("김치"),
                Ingredient("설탕"),
                Ingredient("다진마늘"),
                Ingredient("고춧가루")
            ),
            steps = listOf(
                "김치를 먹기 좋은 크기로 잘라 준비합니다",
                "프라이팬에 기름을 두르고 김치를 볶습니다",
                "몇번 뒤적뒤적 거린 후 설탕을 1/2큰술 넣습니다",
                "다진마늘 1/2큰술을 넣습니다",
                "고춧가루 1/2큰술을 넣습니다",
                "냄비에 소금을 1/2큰술 넣고 두부를 데칩니다",
                "두부를 적당히 자른 후 볶은 김치와 함께 먹습니다"
            )
        ),

        Recipe(
            id = 1,
            name = "계란볶음밥",
            time = 10,
            serving = 1,
            ingredients = listOf(
                Ingredient("밥"),
                Ingredient("계란"),
                Ingredient("대파"),
                Ingredient("간장"),
                Ingredient("소금")
            ),
            steps = listOf(
                "대파를 잘게 썰어 준비합니다",
                "프라이팬에 기름을 두르고 대파를 볶습니다",
                "계란을 넣고 잘 저어가며 볶습니다",
                "밥을 넣고 계란과 함께 볶습니다",
                "간장 1큰술과 소금을 조금 넣습니다",
                "밥을 골고루 볶은 후 그릇에 담습니다"
            )
        ),

        Recipe(
            id = 2,
            name = "김치볶음밥",
            time = 15,
            serving = 1,
            ingredients = listOf(
                Ingredient("밥"),
                Ingredient("김치"),
                Ingredient("대파"),
                Ingredient("간장"),
                Ingredient("참기름")
            ),
            steps = listOf(
                "김치를 먹기 좋은 크기로 잘라 준비합니다",
                "대파를 잘게 썰어 준비합니다",
                "프라이팬에 기름을 두르고 대파를 볶습니다",
                "김치를 넣고 충분히 볶습니다",
                "밥을 넣고 김치와 함께 골고루 볶습니다",
                "간장 1큰술을 넣고 볶습니다",
                "불을 끄고 참기름을 조금 넣어 섞습니다"
            )
        ),

        Recipe(
            id = 3,
            name = "간장계란밥",
            time = 5,
            serving = 1,
            ingredients = listOf(
                Ingredient("밥"),
                Ingredient("계란"),
                Ingredient("간장"),
                Ingredient("참기름")
            ),
            steps = listOf(
                "계란을 프라이팬에 넣고 프라이합니다",
                "따뜻한 밥을 그릇에 담습니다",
                "밥 위에 계란 프라이를 올립니다",
                "간장 1큰술을 넣습니다",
                "참기름을 조금 넣고 잘 비벼 먹습니다"
            )
        ),

        Recipe(
            id = 4,
            name = "참치마요 덮밥",
            time = 10,
            serving = 1,
            ingredients = listOf(
                Ingredient("밥"),
                Ingredient("참치캔"),
                Ingredient("계란"),
                Ingredient("마요네즈"),
                Ingredient("간장")
            ),
            steps = listOf(
                "참치캔의 기름을 빼고 준비합니다",
                "계란을 풀어 스크램블 에그를 만듭니다",
                "따뜻한 밥을 그릇에 담습니다",
                "밥 위에 참치와 계란을 올립니다",
                "간장 1큰술을 넣습니다",
                "마요네즈를 원하는 만큼 뿌려 완성합니다"
            )
        ),

        Recipe(
            id = 5,
            name = "김치찌개",
            time = 25,
            serving = 2,
            ingredients = listOf(
                Ingredient("김치"),
                Ingredient("두부"),
                Ingredient("대파"),
                Ingredient("다진마늘"),
                Ingredient("고춧가루")
            ),
            steps = listOf(
                "김치를 먹기 좋은 크기로 잘라 준비합니다",
                "냄비에 김치를 넣고 살짝 볶습니다",
                "물을 넣고 끓입니다",
                "다진마늘 1/2큰술과 고춧가루 1큰술을 넣습니다",
                "두부를 먹기 좋은 크기로 잘라 넣습니다",
                "대파를 넣고 조금 더 끓입니다",
                "재료가 충분히 익으면 불을 끄고 완성합니다"
            )
        )
    )
}