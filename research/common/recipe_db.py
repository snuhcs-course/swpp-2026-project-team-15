from typing import List, Dict, Optional
from common.models import (
    RecipeCategory, IngredientRole, CanonicalIngredient, Recipe, RecipeIngredient, RecipeStep
)

# Standard Canonical Ingredients (Direct Allergen Attributes & Confusable Metadata)
CANONICAL_INGREDIENTS: Dict[int, CanonicalIngredient] = {
    # Core (Proteins / Carbs)
    1: CanonicalIngredient(id=1, name="돼지고기", role=IngredientRole.CORE, category="육류", standard_unit="g", allergens=["돼지고기"]),
    2: CanonicalIngredient(id=2, name="차돌박이", role=IngredientRole.CORE, category="육류", standard_unit="g", allergens=["쇠고기"]),
    3: CanonicalIngredient(id=3, name="닭가슴살", role=IngredientRole.CORE, category="육류", standard_unit="g", allergens=["닭고기"]),
    4: CanonicalIngredient(id=4, name="두부", role=IngredientRole.CORE, category="두류", standard_unit="모", allergens=["대두"]),
    5: CanonicalIngredient(id=5, name="순두부", role=IngredientRole.CORE, category="두류", standard_unit="봉", allergens=["대두"]),
    6: CanonicalIngredient(id=6, name="계란", role=IngredientRole.CORE, category="난류", standard_unit="개", allergens=["난류"]),
    7: CanonicalIngredient(id=7, name="캔참치", role=IngredientRole.CORE, category="수산가공품", standard_unit="캔", allergens=["고등어/참치"]),
    8: CanonicalIngredient(id=8, name="비엔나소시지", role=IngredientRole.CORE, category="육가공품", standard_unit="개", allergens=["돼지고기"]),
    9: CanonicalIngredient(id=9, name="밥", role=IngredientRole.CORE, category="곡류", standard_unit="공기", allergens=[]),
    10: CanonicalIngredient(id=10, name="라면사리", role=IngredientRole.CORE, category="면류", standard_unit="개", allergens=["밀"]),

    # Sub (Vegetables / Secondary)
    20: CanonicalIngredient(id=20, name="신김치", role=IngredientRole.SUB, category="채소/절임류", standard_unit="g", allergens=[]),
    21: CanonicalIngredient(id=21, name="대파", role=IngredientRole.SUB, category="채소류", standard_unit="대", allergens=[]),
    22: CanonicalIngredient(id=22, name="쪽파", role=IngredientRole.SUB, category="채소류", standard_unit="대", allergens=[]),
    23: CanonicalIngredient(id=23, name="양파", role=IngredientRole.SUB, category="채소류", standard_unit="개", allergens=[]),
    24: CanonicalIngredient(id=24, name="콩나물", role=IngredientRole.SUB, category="채소류", standard_unit="g", allergens=[]),
    25: CanonicalIngredient(id=25, name="애호박", role=IngredientRole.SUB, category="채소류", standard_unit="개", allergens=[], confusables=["단호박", "늙은호박", "주키니"]),
    26: CanonicalIngredient(id=26, name="단호박", role=IngredientRole.SUB, category="채소류", standard_unit="개", allergens=[], confusables=["애호박", "늙은호박"]),
    27: CanonicalIngredient(id=27, name="버섯", role=IngredientRole.SUB, category="버섯류", standard_unit="개", allergens=[]),

    # Pantry (Condiments / Sauces)
    40: CanonicalIngredient(id=40, name="진간장", role=IngredientRole.PANTRY, category="장류", standard_unit="큰술", allergens=["대두", "밀"], confusables=["국간장", "맛간장", "조선간장"]),
    41: CanonicalIngredient(id=41, name="국간장", role=IngredientRole.PANTRY, category="장류", standard_unit="큰술", allergens=["대두", "밀"], confusables=["진간장", "양조간장"]),
    42: CanonicalIngredient(id=42, name="고추장", role=IngredientRole.PANTRY, category="장류", standard_unit="큰술", allergens=["대두", "밀"]),
    43: CanonicalIngredient(id=43, name="된장", role=IngredientRole.PANTRY, category="장류", standard_unit="큰술", allergens=["대두"]),
    44: CanonicalIngredient(id=44, name="다진마늘", role=IngredientRole.PANTRY, category="양념류", standard_unit="큰술", allergens=[]),
    45: CanonicalIngredient(id=45, name="고춧가루", role=IngredientRole.PANTRY, category="양념류", standard_unit="큰술", allergens=[]),
    46: CanonicalIngredient(id=46, name="참기름", role=IngredientRole.PANTRY, category="유지류", standard_unit="큰술", allergens=["참깨"]),
    47: CanonicalIngredient(id=47, name="식용유", role=IngredientRole.PANTRY, category="유지류", standard_unit="큰술", allergens=[]),
    48: CanonicalIngredient(id=48, name="소금", role=IngredientRole.PANTRY, category="조미료", standard_unit="작은술", allergens=[]),
    49: CanonicalIngredient(id=49, name="설탕", role=IngredientRole.PANTRY, category="조미료", standard_unit="큰술", allergens=[]),
    50: CanonicalIngredient(id=50, name="식초", role=IngredientRole.PANTRY, category="조미료", standard_unit="큰술", allergens=[]),
    51: CanonicalIngredient(id=51, name="새우젓", role=IngredientRole.PANTRY, category="젓갈류", standard_unit="작은술", allergens=["갑각류"], confusables=["멸치액젓", "까나리액젓"]),
    52: CanonicalIngredient(id=52, name="멸치액젓", role=IngredientRole.PANTRY, category="젓갈류", standard_unit="작은술", allergens=["어류"], confusables=["새우젓", "까나리액젓"]),
}

SAMPLE_RECIPES: List[Recipe] = [
    # ----------------- 1. 주식 (MAIN) -----------------
    Recipe(
        id=1,
        title="돼지고기 김치찌개",
        source="농림수산식품교육문화정보원",
        category=RecipeCategory.MAIN,
        base_servings=2,
        cooking_time_minutes=25,
        allergens=["돼지고기", "대두"],
        ingredients=[
            RecipeIngredient(ingredient_id=1, name="돼지고기", amount=100, unit="g", role=IngredientRole.CORE),
            RecipeIngredient(ingredient_id=20, name="신김치", amount=150, unit="g", role=IngredientRole.SUB),
            RecipeIngredient(ingredient_id=4, name="두부", amount=0.5, unit="모", role=IngredientRole.CORE),
            RecipeIngredient(ingredient_id=21, name="대파", amount=0.5, unit="대", role=IngredientRole.SUB),
            RecipeIngredient(ingredient_id=44, name="다진마늘", amount=0.5, unit="큰술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=45, name="고춧가루", amount=1.0, unit="큰술", role=IngredientRole.PANTRY),
        ],
        steps=[
            RecipeStep(step_number=1, instruction="냄비에 참기름을 두르고 돼지고기와 김치를 볶는다.", duration_minutes=3),
            RecipeStep(step_number=2, instruction="물 400ml와 다진마늘, 고춧가루를 넣고 15분간 끓인다.", duration_minutes=15),
            RecipeStep(step_number=3, instruction="두부와 대파를 넣고 2분간 가볍게 끓여 마무리한다.", duration_minutes=2),
        ]
    ),
    Recipe(
        id=2,
        title="구수한 차돌 된장찌개",
        source="농림수산식품교육문화정보원",
        category=RecipeCategory.MAIN,
        base_servings=2,
        cooking_time_minutes=20,
        allergens=["쇠고기", "대두"],
        ingredients=[
            RecipeIngredient(ingredient_id=2, name="차돌박이", amount=80, unit="g", role=IngredientRole.CORE),
            RecipeIngredient(ingredient_id=4, name="두부", amount=0.5, unit="모", role=IngredientRole.CORE),
            RecipeIngredient(ingredient_id=25, name="애호박", amount=0.5, unit="개", role=IngredientRole.SUB),
            RecipeIngredient(ingredient_id=23, name="양파", amount=0.5, unit="개", role=IngredientRole.SUB),
            RecipeIngredient(ingredient_id=43, name="된장", amount=2.0, unit="큰술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=44, name="다진마늘", amount=0.5, unit="큰술", role=IngredientRole.PANTRY),
        ],
        steps=[
            RecipeStep(step_number=1, instruction="냄비에 차돌박이를 살짝 볶는다.", duration_minutes=2),
            RecipeStep(step_number=2, instruction="물 500ml를 붓고 된장과 마늘을 푼 뒤 애호박과 양파를 넣고 끓인다.", duration_minutes=12),
            RecipeStep(step_number=3, instruction="두부를 넣고 3분간 더 끓여 완성한다.", duration_minutes=3),
        ]
    ),
    Recipe(
        id=3,
        title="매콤 제육볶음",
        source="농림수산식품교육문화정보원",
        category=RecipeCategory.MAIN,
        base_servings=2,
        cooking_time_minutes=15,
        allergens=["돼지고기", "대두", "밀"],
        ingredients=[
            RecipeIngredient(ingredient_id=1, name="돼지고기", amount=150, unit="g", role=IngredientRole.CORE),
            RecipeIngredient(ingredient_id=23, name="양파", amount=0.5, unit="개", role=IngredientRole.SUB),
            RecipeIngredient(ingredient_id=21, name="대파", amount=0.5, unit="대", role=IngredientRole.SUB),
            RecipeIngredient(ingredient_id=42, name="고추장", amount=1.5, unit="큰술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=40, name="진간장", amount=1.0, unit="큰술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=49, name="설탕", amount=1.0, unit="큰술", role=IngredientRole.PANTRY),
        ],
        steps=[
            RecipeStep(step_number=1, instruction="팬에 기름을 두르고 돼지고기를 강불에 볶는다.", duration_minutes=4),
            RecipeStep(step_number=2, instruction="양념과 양파를 넣고 빠르게 볶는다.", duration_minutes=5),
            RecipeStep(step_number=3, instruction="대파를 얹고 불을 끈 뒤 잔열로 섞어 완성한다.", duration_minutes=1),
        ]
    ),
    Recipe(
        id=4,
        title="초간단 참치 김치볶음밥",
        source="우리의식탁",
        category=RecipeCategory.MAIN,
        base_servings=1,
        cooking_time_minutes=10,
        allergens=["고등어/참치", "대두", "참깨"],
        ingredients=[
            RecipeIngredient(ingredient_id=7, name="캔참치", amount=1.0, unit="캔", role=IngredientRole.CORE),
            RecipeIngredient(ingredient_id=20, name="신김치", amount=80, unit="g", role=IngredientRole.SUB),
            RecipeIngredient(ingredient_id=9, name="밥", amount=1.0, unit="공기", role=IngredientRole.CORE),
            RecipeIngredient(ingredient_id=21, name="대파", amount=0.25, unit="대", role=IngredientRole.SUB),
            RecipeIngredient(ingredient_id=46, name="참기름", amount=1.0, unit="큰술", role=IngredientRole.PANTRY),
        ],
        steps=[
            RecipeStep(step_number=1, instruction="팬에 기름을 두르고 대파와 김치, 참치를 볶는다.", duration_minutes=4),
            RecipeStep(step_number=2, instruction="밥을 넣고 볶아낸다.", duration_minutes=3),
            RecipeStep(step_number=3, instruction="참기름을 둘러 마무리한다.", duration_minutes=1),
        ]
    ),
    Recipe(
        id=5,
        title="맑은 두부 계란국",
        source="만개의레시피",
        category=RecipeCategory.MAIN,
        base_servings=1,
        cooking_time_minutes=10,
        allergens=["난류", "대두", "밀", "갑각류"],
        ingredients=[
            RecipeIngredient(ingredient_id=6, name="계란", amount=2.0, unit="개", role=IngredientRole.CORE),
            RecipeIngredient(ingredient_id=4, name="두부", amount=0.5, unit="모", role=IngredientRole.CORE),
            RecipeIngredient(ingredient_id=21, name="대파", amount=0.25, unit="대", role=IngredientRole.SUB),
            RecipeIngredient(ingredient_id=41, name="국간장", amount=0.5, unit="큰술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=51, name="새우젓", amount=0.5, unit="작은술", role=IngredientRole.PANTRY),
        ],
        steps=[
            RecipeStep(step_number=1, instruction="물 400ml에 국간장과 새우젓으로 간을 맞추고 끓인다.", duration_minutes=4),
            RecipeStep(step_number=2, instruction="두부와 계란물을 풀고 대파를 얹어 마무리한다.", duration_minutes=3),
        ]
    ),

    # ----------------- 2. 부식 (SIDE) -----------------
    Recipe(
        id=6,
        title="폭신폭신 대파 계란말이",
        source="만개의레시피",
        category=RecipeCategory.SIDE,
        base_servings=1,
        cooking_time_minutes=10,
        allergens=["난류"],
        ingredients=[
            RecipeIngredient(ingredient_id=6, name="계란", amount=3.0, unit="개", role=IngredientRole.CORE),
            RecipeIngredient(ingredient_id=21, name="대파", amount=0.25, unit="대", role=IngredientRole.SUB),
            RecipeIngredient(ingredient_id=48, name="소금", amount=0.25, unit="작은술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=47, name="식용유", amount=1.0, unit="큰술", role=IngredientRole.PANTRY),
        ],
        steps=[
            RecipeStep(step_number=1, instruction="볼에 계란을 풀고 송송 썬 대파와 소금을 섞는다.", duration_minutes=2),
            RecipeStep(step_number=2, instruction="팬에 기름을 두르고 약불에서 계란물을 부어가며 만다.", duration_minutes=6),
        ]
    ),
    Recipe(
        id=7,
        title="소시지 야채볶음",
        source="농림수산식품교육문화정보원",
        category=RecipeCategory.SIDE,
        base_servings=1,
        cooking_time_minutes=10,
        allergens=["돼지고기", "대두"],
        ingredients=[
            RecipeIngredient(ingredient_id=8, name="비엔나소시지", amount=8.0, unit="개", role=IngredientRole.CORE),
            RecipeIngredient(ingredient_id=23, name="양파", amount=0.5, unit="개", role=IngredientRole.SUB),
            RecipeIngredient(ingredient_id=40, name="진간장", amount=0.5, unit="큰술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=49, name="설탕", amount=0.5, unit="큰술", role=IngredientRole.PANTRY),
        ],
        steps=[
            RecipeStep(step_number=1, instruction="칼집 낸 소시지와 양파를 팬에 볶는다.", duration_minutes=4),
            RecipeStep(step_number=2, instruction="간장과 설탕을 넣고 조린다.", duration_minutes=2),
        ]
    ),
    Recipe(
        id=8,
        title="새우젓 애호박볶음",
        source="만개의레시피",
        category=RecipeCategory.SIDE,
        base_servings=2,
        cooking_time_minutes=8,
        allergens=["갑각류"],
        ingredients=[
            RecipeIngredient(ingredient_id=25, name="애호박", amount=1.0, unit="개", role=IngredientRole.SUB),
            RecipeIngredient(ingredient_id=21, name="대파", amount=0.25, unit="대", role=IngredientRole.SUB),
            RecipeIngredient(ingredient_id=51, name="새우젓", amount=0.5, unit="큰술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=44, name="다진마늘", amount=0.5, unit="작은술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=46, name="참기름", amount=0.5, unit="큰술", role=IngredientRole.PANTRY),
        ],
        steps=[
            RecipeStep(step_number=1, instruction="반달 썬 애호박을 기름 두른 팬에 볶는다.", duration_minutes=3),
            RecipeStep(step_number=2, instruction="새우젓과 다진마늘을 넣고 간이 배게 볶아 참기름으로 마무리한다.", duration_minutes=4),
        ]
    ),
    Recipe(
        id=9,
        title="아삭한 콩나물 무침",
        source="만개의레시피",
        category=RecipeCategory.SIDE,
        base_servings=2,
        cooking_time_minutes=8,
        allergens=["참깨"],
        ingredients=[
            RecipeIngredient(ingredient_id=24, name="콩나물", amount=150, unit="g", role=IngredientRole.SUB),
            RecipeIngredient(ingredient_id=21, name="대파", amount=0.2, unit="대", role=IngredientRole.SUB),
            RecipeIngredient(ingredient_id=44, name="다진마늘", amount=0.3, unit="작은술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=48, name="소금", amount=0.3, unit="작은술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=46, name="참기름", amount=0.5, unit="큰술", role=IngredientRole.PANTRY),
        ],
        steps=[
            RecipeStep(step_number=1, instruction="끓는 물에 콩나물을 3분간 데친 후 찬물에 헹군다.", duration_minutes=4),
            RecipeStep(step_number=2, instruction="물기를 짠 후 다진마늘, 소금, 참기름으로 조물조물 무친다.", duration_minutes=3),
        ]
    ),

    # ----------------- 3. 양념/소스 (CONDIMENT) -----------------
    Recipe(
        id=10,
        title="만능 마늘간장 비빔장",
        source="만개의레시피",
        category=RecipeCategory.CONDIMENT,
        base_servings=2,
        cooking_time_minutes=3,
        allergens=["대두", "밀", "참깨"],
        ingredients=[
            RecipeIngredient(ingredient_id=40, name="진간장", amount=2.0, unit="큰술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=44, name="다진마늘", amount=1.0, unit="큰술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=45, name="고춧가루", amount=0.5, unit="큰술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=46, name="참기름", amount=1.0, unit="큰술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=49, name="설탕", amount=0.5, unit="큰술", role=IngredientRole.PANTRY),
        ],
        steps=[
            RecipeStep(step_number=1, instruction="볼에 간장, 마늘, 고춧가루, 참기름, 설탕을 넣고 고루 섞는다.", duration_minutes=3),
        ]
    ),
    Recipe(
        id=11,
        title="고깃집 양파절임 초간장 소스",
        source="만개의레시피",
        category=RecipeCategory.CONDIMENT,
        base_servings=2,
        cooking_time_minutes=3,
        allergens=["대두", "밀"],
        ingredients=[
            RecipeIngredient(ingredient_id=40, name="진간장", amount=2.0, unit="큰술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=50, name="식초", amount=1.5, unit="큰술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=49, name="설탕", amount=1.0, unit="큰술", role=IngredientRole.PANTRY),
            RecipeIngredient(ingredient_id=23, name="양파", amount=0.5, unit="개", role=IngredientRole.SUB),
        ],
        steps=[
            RecipeStep(step_number=1, instruction="간장, 식초, 설탕을 1:1:1 비율로 섞어 얇게 채 썬 양파에 붓는다.", duration_minutes=3),
        ]
    ),
]
