package com.example.mylittlechef.integration

import com.example.mylittlechef.data.recipes.*
import com.example.mylittlechef.model.*
import com.example.mylittlechef.domain.*
import com.google.gson.Gson
import com.google.gson.JsonParser
import kotlinx.coroutines.runBlocking
import org.junit.Assert.*
import org.junit.Test

/** US02/04/05: source fixture is actual synthetic SQLite/scripted-provider API output. */
class RecipeContractTest {
    private val gson = Gson()
    private fun fixture(): String = requireNotNull(javaClass.getResource("/recipe-integration-response.json")).readText()
    private fun catalog() = IngredientCatalogDto("a".repeat(64), listOf(
        CatalogIngredientDto(32, "계란"), CatalogIngredientDto(204, "물"), CatalogIngredientDto(5, "두부")))

    @Test fun exactNamesAliasUnknownAndDuplicates() {
        val resolved = catalog().resolve(listOf(" 계란 ", "달걀", "두부", "", "미등록"))
        assertEquals(listOf(32L, 5L), resolved.ids)
        assertEquals(listOf("미등록"), resolved.unmapped)
    }

    @Test fun ambiguousNameNeverFabricatesAnId() {
        val data = IngredientCatalogDto("a".repeat(64), listOf(CatalogIngredientDto(1, "Egg"), CatalogIngredientDto(2, "egg")))
        assertEquals(emptyList<Long>(), data.resolve(listOf("EGG")).ids)
        assertEquals(listOf("EGG"), data.resolve(listOf("EGG")).unmapped)
    }

    @Test fun malformedCatalogRejected() {
        assertTrue(runCatching { catalog().copy(version = "bad").resolve(emptyList()) }.isFailure)
        assertTrue(runCatching { catalog().copy(ingredients = null).resolve(emptyList()) }.isFailure)
        assertTrue(runCatching { catalog().copy(ingredients = listOf(CatalogIngredientDto(0, "x"))).resolve(emptyList()) }.isFailure)
    }

    @Test fun serverFixtureRetainsOriginalAndMixedRevisionStates() {
        val result = gson.fromJson(fixture(), IdRecommendationsDto::class.java).mapped(listOf(1, 2))
        assertEquals(20L, result.first().id)
        val first = result.first()
        assertEquals(0, first.filteringMissingCount)
        assertEquals(1, first.missing!!.size) // Salt is absent but excluded from filtering counts.
        assertEquals(5, first.source!!.ingredients.size) // Repeated source rows retained.
        assertTrue(first.source!!.steps.last().contains("Source tip"))
        assertEquals("4 servings", first.source!!.servings)
        assertEquals("revised", first.revision!!.status)
        assertEquals("Mock revised", first.revision!!.suggestion!!.name)
        assertTrue(result.any { it.revision!!.status == "refused" })
        assertTrue(result.any { it.revision!!.status == "failed" })
        assertTrue(result.any { it.revision!!.status == "not_attempted" })
    }

    @Test fun malformedMissingAndUnknownOutcomesRejected() {
        for (field in listOf("original", "filtering", "revision")) {
            val body = JsonParser.parseString(fixture()).asJsonObject
            body.getAsJsonArray("recipes")[0].asJsonObject.remove(field)
            assertTrue(runCatching { gson.fromJson(body, IdRecommendationsDto::class.java).mapped(listOf(1, 2)) }.isFailure)
        }
        val body = JsonParser.parseString(fixture()).asJsonObject
        body.getAsJsonArray("recipes")[0].asJsonObject.getAsJsonObject("revision").addProperty("status", "unexpected")
        assertTrue(runCatching { gson.fromJson(body, IdRecommendationsDto::class.java).mapped(listOf(1, 2)) }.isFailure)
    }

    @Test fun missingFilteringCountCannotBecomeZeroSilently() {
        val body = JsonParser.parseString(fixture()).asJsonObject
        body.getAsJsonArray("recipes")[0].asJsonObject.getAsJsonObject("filtering").remove("missing_count")
        assertTrue(runCatching { gson.fromJson(body, IdRecommendationsDto::class.java).mapped(listOf(1, 2)) }.isFailure)
    }

    @Test fun filteringCountDrivesMissingSortWithoutReplacingOwnerSorter() {
        val recipe = Recipe(1, "x", 5, 1, emptyList(), emptyList(), missing = listOf(Ingredient("salt")), filteringMissingCount = 0)
        val other = recipe.copy(id = 2, missing = emptyList(), filteringMissingCount = 1)
        assertEquals(listOf(1L, 2L), sortRecipes(listOf(other, recipe), RecipeSortType.FEWEST_MISSING).map { it.id })
    }

    @Test fun adapterResolvesBeforeCallingIdEndpoint() = runBlocking {
        var observed: IdRecommendRequest? = null
        var token: String? = null
        val api = object : IdRecipeApi {
            override suspend fun catalog() = this@RecipeContractTest.catalog()
            override suspend fun recommend(request: IdRecommendRequest, version: String): IdRecommendationsDto {
                observed = request; token = version
                return gson.fromJson(fixture(), IdRecommendationsDto::class.java)
            }
            override suspend fun source(id: Long): SourceRecipeDto = error("Not used")
        }
        val batch = NetworkRecipeSource(api).recommend(listOf("달걀", "unknown"))
        assertEquals(listOf(32L), observed!!.ingredientIds)
        assertEquals("a".repeat(64), token)
        assertEquals(listOf("unknown"), batch.unmapped)
        assertEquals(6, batch.recipes.size)
    }
}
