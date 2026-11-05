// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.viewmodel

import com.example.mylittlechef.data.remote.*
import com.google.gson.Gson
import com.google.gson.JsonParser
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.*
import org.junit.Assert.assertEquals
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class RecipeAssumedPolicyTest {
    private fun fake(global: List<Int>, candidate: List<Int>, revised: List<Int>?): OnDemandRecipeApi {
        val source = SourceRecipeDto(7,"원본","10분","1인분",
            listOf(SourceIngredientDto(1,"계란","1개"),SourceIngredientDto(2,"양파","1개")),
            listOf(SourceStepDto(1,"조리")))
        val gson = Gson()
        return object : OnDemandRecipeApi {
            override suspend fun recipeCatalog() = RecipeCatalogDto(listOf(CatalogItemDto(1,"계란",listOf("계란"))))
            override suspend fun candidates(request: InventoryIdsDto): CandidatesDto {
                val raw = JsonParser.parseString(gson.toJson(CandidatesDto(
                    listOf(CandidateDto(7,source,listOf(source.ingredients[1]),true)),global))).asJsonObject
                raw.getAsJsonArray("recipes")[0].asJsonObject.add("assumed_ingredient_ids",gson.toJsonTree(candidate))
                return gson.fromJson(raw,CandidatesDto::class.java)
            }
            override suspend fun reviseRecipe(id: Long, request: InventoryIdsDto): SingleRevisionDto {
                val result = RevisionResultDto("조정",emptyList(),RevisedRecipeDto("제안","1인분",
                    listOf(source.ingredients[0],SourceIngredientDto(999,"물",null)),source.steps))
                val raw = JsonParser.parseString(gson.toJson(SingleRevisionDto(id,source,RevisionOutcomeDto("revised",result,null)))).asJsonObject
                if (revised != null) raw.add("assumed_ingredient_ids",gson.toJsonTree(revised))
                return gson.fromJson(raw,SingleRevisionDto::class.java)
            }
        }
    }

    @Test fun candidateSpecificAssumptionsAreUsedForLegacySingleResponse() = runTest {
        val session=RecipeRevisionSession(fake(emptyList(),listOf(999),null),backgroundScope)
        session.updateContext(RecipeContext(listOf("계란")));session.loadCandidates();session.request(7);runCurrent()
        assertEquals(emptyList<String>(),session.state(7).recipe!!.missing!!.map { it.name })
    }

    @Test fun explicitSingleResponseAssumptionsOverrideOlderListPolicy() = runTest {
        val session=RecipeRevisionSession(fake(listOf(999),listOf(999),emptyList()),backgroundScope)
        session.updateContext(RecipeContext(listOf("계란")));session.loadCandidates();session.request(7);runCurrent()
        assertEquals(listOf("물"),session.state(7).recipe!!.missing!!.map { it.name })
    }
}
