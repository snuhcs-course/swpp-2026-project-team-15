// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.dish

import com.example.mylittlechef.data.remote.DishAdaptResponse
import com.example.mylittlechef.data.remote.DishSuggestResponse
import com.example.mylittlechef.data.remote.DishVideosResponse
import com.example.mylittlechef.domain.DishSort
import com.example.mylittlechef.domain.sortDishes
import com.example.mylittlechef.domain.toAdaptation
import com.example.mylittlechef.domain.toDish
import com.example.mylittlechef.domain.toVideo
import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class DishDtoTest {
    private val gson = Gson()

    private val suggestJson = """
        {"source":"llm","dishes":[
          {"id":"kimchi-fried-rice","name":"김치볶음밥","category":"볶음밥","have":["김치","쌀"],"missing":["대파"],
           "reason":"김치와 밥이 있어요","keywords":["돼지고기김치볶음밥"],
           "search_url":"https://www.youtube.com/results?search_query=x"},
          {"id":null,"name":"이름만 없음"},
          {"id":"plain","name":"계란말이"}
        ]}
    """.trimIndent()

    @Test fun suggestResponseMapsToDishesAndDropsBrokenEntries() {
        val response = gson.fromJson(suggestJson, DishSuggestResponse::class.java)
        assertEquals("llm", response.source)
        val dishes = response.dishes!!.mapNotNull { it.toDish() }
        assertEquals(listOf("김치볶음밥", "계란말이"), dishes.map { it.name })
        val first = dishes[0]
        assertEquals(listOf("김치", "쌀"), first.have)
        assertEquals(listOf("대파"), first.missing)
    }

    @Test fun videoEntriesNeedAValidIdAndKeepOnlyHttpsThumbnails() {
        val json = """{"videos":[{"video_id":"dQw4w9WgXcQ","title":"제목","channel":"채널","thumbnail_url":"https://i.ytimg.com/x.jpg"},
            {"video_id":"bad id","title":"깨진","channel":"x","thumbnail_url":"https://x"},
            {"video_id":"a_b-c1234AB","title":"막힌","channel":"y","thumbnail_url":"http://insecure"}]}"""
        val videos = gson.fromJson(json, DishVideosResponse::class.java).videos!!.mapNotNull { it.toVideo() }
        assertEquals(listOf("dQw4w9WgXcQ", "a_b-c1234AB"), videos.map { it.videoId })
        assertEquals("https://i.ytimg.com/x.jpg", videos[0].thumbnailUrl)
        assertNull(videos[1].thumbnailUrl)
    }

    @Test fun missingFieldsBecomeEmptyListsAndASafeSearchLink() {
        val plain = gson.fromJson(suggestJson, DishSuggestResponse::class.java).dishes!!.mapNotNull { it.toDish() }[1]
        assertTrue(plain.have.isEmpty() && plain.missing.isEmpty())
        assertTrue(plain.searchUrl.startsWith("https://www.youtube.com/results?search_query="))
    }

    @Test fun adaptResponseKeepsOnlyCompleteSubstitutions() {
        val json = """{"dish_id":"d","substitutions":[{"missing":"대파","suggestion":"양파로 대체","uses":["양파"]},
            {"missing":"","suggestion":"x"},{"missing":"파","suggestion":null}],"skip_ok":["깨"],"note":"참고","source":"llm"}"""
        val a = gson.fromJson(json, DishAdaptResponse::class.java).toAdaptation()
        assertEquals(1, a.substitutions.size)
        assertEquals("양파로 대체", a.substitutions[0].suggestion)
        assertEquals(listOf("양파"), a.substitutions[0].uses)
        assertEquals(listOf("깨"), a.skipOk)
        assertEquals("참고", a.note)
    }

    @Test fun sortingFollowsTheChosenOrder() {
        val dishes = gson.fromJson(
            """{"dishes":[{"id":"a","name":"나","have":["1"],"missing":["x","y"]},
                {"id":"b","name":"가","have":["1","2"],"missing":["x"]},
                {"id":"c","name":"다","have":[],"missing":[]}]}""",
            DishSuggestResponse::class.java
        ).dishes!!.mapNotNull { it.toDish() }
        assertEquals(listOf("c", "b", "a"), sortDishes(dishes, DishSort.FEWEST_MISSING).map { it.id })
        assertEquals(listOf("b", "a", "c"), sortDishes(dishes, DishSort.MOST_HAVE).map { it.id })
        assertEquals(listOf("b", "a", "c"), sortDishes(dishes, DishSort.NAME).map { it.id })
    }

    // Server field added 2026-11-19 so a card shows its photo before the dish is opened.
    @Test
    fun suggestionPhotoIsKeptOnlyFromYouTubesImageHost() {
        val json = """
            {"source":"llm","dishes":[
              {"id":"a","name":"A","thumbnail_url":"https://i.ytimg.com/vi/abcdefghijk/mqdefault.jpg"},
              {"id":"b","name":"B","thumbnail_url":"https://example.com/x.jpg"},
              {"id":"c","name":"C"}
            ]}
        """.trimIndent()
        val dishes = gson.fromJson(json, DishSuggestResponse::class.java).dishes.orEmpty().mapNotNull { it.toDish() }
        assertEquals("https://i.ytimg.com/vi/abcdefghijk/mqdefault.jpg", dishes[0].thumbnailUrl)
        assertNull(dishes[1].thumbnailUrl)
        assertNull(dishes[2].thumbnailUrl)
    }
}
