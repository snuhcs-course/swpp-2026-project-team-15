// AI-assisted with Codex, 2026-11-02; human review pending.
package com.example.mylittlechef.domain

import com.example.mylittlechef.model.Ingredient
import org.junit.Assert.*
import org.junit.Test

class IngredientPresentationTest {
    private val header = "ingredient_id,name,category_key,category,icon_key,background_color,review_required,review_note\r\n"
    private fun catalog() = IngredientPresentationCatalog.fromCsv(header +
        "103,다진마늘,vegetables,채소·버섯,garlic,#EDE9D7,false,\r\n" +
        "169,마늘,vegetables,채소·버섯,garlic,#EDE9D7,false,\r\n" +
        "32,계란,eggs_dairy,달걀·유제품,egg,#F8DFC8,false,\r\n" +
        "70,김치,prepared,김치·절임·간편식,kimchi,#E8B7A5,false,\r\n" +
        "284,소금,seasonings,양념·소스·기름,seasoning,#E5EBF0,false,\r\n")

    @Test fun parsesBomAndQuotedFieldsWithoutChangingNames() {
        val catalog = IngredientPresentationCatalog.fromCsv("\uFEFF" + header +
            "1,\"재료,이름\",other,기타·미분류,generic,#E2E5E7,true,\"첫 줄\n두 번째 \"\"메모\"\"\"\r\n")
        assertEquals("generic", catalog.appearanceFor("재료,이름").iconKey)
        assertEquals("#E2E5E7", catalog.appearanceFor("재료,이름").backgroundColor)
    }

    @Test fun unknownNamesUseOtherAndGenericWithoutDroppingIngredients() {
        val input = listOf(Ingredient("처음보는재료"), Ingredient("계란"))
        assertEquals("other", catalog().appearanceFor(input[0].name).categoryKey)
        assertEquals("generic", catalog().appearanceFor(input[0].name).iconKey)
        assertEquals(2, sortFridgeIngredients(input, FridgeSortType.CATEGORY, catalog()).size)
    }

    @Test fun sortsCategoriesThenKoreanNamesWithoutChangingStoredOrderOrIdentity() {
        val names = listOf("소금", "마늘", "김치", "다진마늘", "계란", "처음보는재료")
        val input = names.map(::Ingredient)
        assertEquals(listOf("다진마늘", "마늘", "계란", "김치", "소금", "처음보는재료"),
            sortFridgeIngredients(input, FridgeSortType.CATEGORY, catalog()).map { it.name })
        assertEquals(names, input.map { it.name })
        val shared = sortFridgeIngredients(input, FridgeSortType.CATEGORY, catalog())
        assertSame(input[3], shared[0])
        assertSame(input[1], shared[1])
    }

    @Test fun alphabeticalIgnoresCategoryAndPreservesSharedIconNames() {
        val input = listOf("소금", "마늘", "김치", "다진마늘", "계란").map(::Ingredient)
        assertEquals(listOf("계란", "김치", "다진마늘", "마늘", "소금"),
            sortFridgeIngredients(input, FridgeSortType.ALPHABETICAL, catalog()).map { it.name })
    }

    @Test fun addedOrderIsAnUnsortedCopyOfInventoryOrder() {
        val added = FridgeSortType.entries.singleOrNull { it.label == "추가순" }
        assertNotNull("The menu must include added order", added)
        val input = listOf("소금", "마늘", "김치", "다진마늘").map(::Ingredient)
        val displayed = sortFridgeIngredients(input, requireNotNull(added), catalog())
        assertEquals(input, displayed)
        assertNotSame(input, displayed)
    }

    @Test fun aliasesOnlyChangeAppearanceAndNotInventoryNames() {
        val input = listOf(Ingredient("달걀"), Ingredient("계란"))
        assertEquals("egg", catalog().appearanceFor("달걀").iconKey)
        assertEquals(listOf("달걀", "계란"), sortFridgeIngredients(input, FridgeSortType.CATEGORY, catalog()).map { it.name }.sortedDescending())
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsDuplicateNamesInsteadOfSilentlyPickingOne() {
        IngredientPresentationCatalog.fromCsv(header +
            "1,마늘,vegetables,채소·버섯,garlic,#EDE9D7,false,\n" +
            "2,마늘,vegetables,채소·버섯,garlic,#EDE9D7,false,\n")
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsInvalidColors() {
        IngredientPresentationCatalog.fromCsv(header + "1,마늘,vegetables,채소·버섯,garlic,red,false,\n")
    }
}
