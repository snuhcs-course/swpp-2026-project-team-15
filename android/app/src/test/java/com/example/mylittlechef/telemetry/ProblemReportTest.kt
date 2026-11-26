// AI-generated with Claude Code (Opus 5.5), 2026-11-26; human review pending.
package com.example.mylittlechef.telemetry

import com.example.mylittlechef.domain.ProblemReportInfo
import com.example.mylittlechef.domain.RecentUsage
import com.example.mylittlechef.domain.RecordingTelemetry
import com.example.mylittlechef.domain.ReportFormConfig
import com.example.mylittlechef.domain.Telemetry
import com.example.mylittlechef.domain.Usage
import com.example.mylittlechef.domain.UsageEvent
import com.example.mylittlechef.domain.prefilledReportUrl
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.net.URI
import java.net.URLDecoder

/** The headless base of a future "문제 신고": recent event names and a pre-filled form address. */
class ProblemReportTest {
    private class Recorder : Telemetry {
        val events = mutableListOf<Usage>()
        var flushed = 0
        override fun track(usage: Usage) { events += usage }
        override fun flush() { flushed++ }
    }

    @Test fun theBufferKeepsTheLastTenNamesAndScreensOnly() {
        val recent = RecentUsage()
        val inner = Recorder()
        val telemetry = RecordingTelemetry(inner, recent)
        repeat(12) { telemetry.track(Usage(UsageEvent.DISH_OPEN, dishId = "tofu-soup-$it")) }
        telemetry.track(Usage(UsageEvent.SCREEN_VIEW, screen = "fridge"))
        telemetry.flush()
        val labels = recent.labels()
        assertEquals(10, labels.size)
        assertEquals("screen_view:fridge", labels.last())
        assertTrue(labels.dropLast(1).all { it == "dish_open" }) // no dish id
        assertEquals(13, inner.events.size) // every event still reaches the sender
        assertEquals(1, inner.flushed)
    }

    @Test fun theInfoCleansThePhoneValues() {
        val recent = RecentUsage().apply { add(Usage(UsageEvent.SESSION_START)) }
        val info = ProblemReportInfo.of("1.0.1", "홍길동의 폰", 0, recent)
        assertEquals(1, info.apiLevel)
        assertTrue(Regex("^[A-Za-z0-9 ._()+-]{1,64}$").matches(info.device))
        assertEquals(listOf("session_start"), info.recent)
    }

    private val config = ReportFormConfig(
        "https://docs.google.com/forms/d/e/FORM_ID/viewform", "entry.111", "entry.222", "entry.333", "entry.444"
    )

    @Test fun theFormAddressCarriesEachValueUnderItsEntry() {
        val info = ProblemReportInfo("1.0.1", "Pixel 7 Pro", 34, listOf("screen_view:dishes", "dish_open", "cook_start"))
        val url = prefilledReportUrl(config, info)!!
        assertTrue(url.startsWith("https://docs.google.com/forms/d/e/FORM_ID/viewform?usp=pp_url&"))
        val query = URI(url).rawQuery.split("&").associate {
            val (k, v) = it.split("=", limit = 2); k to URLDecoder.decode(v, "UTF-8")
        }
        assertEquals("1.0.1", query["entry.111"])
        assertEquals("Pixel 7 Pro", query["entry.222"])
        assertEquals("34", query["entry.333"])
        assertEquals("screen_view:dishes > dish_open > cook_start", query["entry.444"])
        assertFalse(url.contains(" "))
    }

    @Test fun aBadConfigurationGivesNoAddress() {
        val info = ProblemReportInfo("1.0.1", "x", 34, emptyList())
        assertNull(prefilledReportUrl(config.copy(baseUrl = "http://docs.google.com/forms/x"), info))
        assertNull(prefilledReportUrl(config.copy(baseUrl = "https://forms/x?usp=pp_url"), info))
        assertNull(prefilledReportUrl(config.copy(recentEntry = "entry.1&evil=1"), info))
        assertNull(prefilledReportUrl(config.copy(versionEntry = ""), info))
    }
}
