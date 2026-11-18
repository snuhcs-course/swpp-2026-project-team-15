// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.dish

import com.example.mylittlechef.domain.DishLinks
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DishLinksTest {
    @Test fun videoIdsMustBeElevenSafeCharacters() {
        assertTrue(DishLinks.isValidVideoId("dQw4w9WgXcQ"))
        assertTrue(DishLinks.isValidVideoId("a_b-c1234AB"))
        assertFalse(DishLinks.isValidVideoId("short"))
        assertFalse(DishLinks.isValidVideoId("dQw4w9WgXcQ\" onload=\""))
        assertFalse(DishLinks.isValidVideoId("dQw4w9WgXc!"))
    }

    @Test fun watchAndEmbedUrlsUseTheOfficialHosts() {
        assertEquals("https://www.youtube.com/watch?v=dQw4w9WgXcQ", DishLinks.watchUrl("dQw4w9WgXcQ"))
        assertEquals(
            "https://www.youtube.com/embed/dQw4w9WgXcQ?playsinline=1&rel=0",
            DishLinks.embedUrl("dQw4w9WgXcQ")
        )
    }

    @Test fun playerPageHostsTheIframePlayerAtFullSizeAndReportsErrors() {
        val html = DishLinks.playerHtml("dQw4w9WgXcQ")
        assertTrue(html.contains("videoId:'dQw4w9WgXcQ'"))
        assertTrue(html.contains("https://www.youtube.com/iframe_api"))
        assertTrue(html.contains("html,body,#p{margin:0;width:100%;height:100%"))
        assertTrue(html.contains("origin:'${DishLinks.EMBED_BASE_URL}'"))
        assertTrue(html.contains("${DishLinks.PLAYER_BRIDGE}.onError("))
        assertTrue(DishLinks.EMBED_PAGE_URL.startsWith(DishLinks.EMBED_BASE_URL))
    }

    @Test fun playerPageRefusesAnInvalidVideoId() {
        val bad = listOf("", "short", "dQw4w9WgXcQ');alert(1);//")
        bad.forEach { id ->
            val failed = runCatching { DishLinks.playerHtml(id) }.isFailure
            assertTrue("accepted $id", failed)
        }
    }

    @Test fun serverSearchLinkIsUsedOnlyForHttpsYouTube() {
        val ok = "https://www.youtube.com/results?search_query=%EA%B9%80%EC%B9%98"
        assertEquals(ok, DishLinks.safeSearchUrl(ok, "김치볶음밥"))
        assertEquals(ok.replace("www.", "m."), DishLinks.safeSearchUrl(ok.replace("www.", "m."), "김치볶음밥"))
        val fallback = DishLinks.safeSearchUrl("http://www.youtube.com/results?x=1", "김치볶음밥")
        assertTrue(fallback.startsWith("https://www.youtube.com/results?search_query="))
        assertTrue(DishLinks.safeSearchUrl("https://evil.example/results", "김치").startsWith("https://www.youtube.com/"))
        assertTrue(DishLinks.safeSearchUrl(null, "김치").contains("%EA%B9%80%EC%B9%98"))
        assertTrue(DishLinks.safeSearchUrl("https://notyoutube.com/x", "김치").startsWith("https://www.youtube.com/"))
    }
}
