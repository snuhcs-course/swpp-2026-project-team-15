// AI-generated with Claude Code (Opus 5.5), 2026-11-26; human review pending.
package com.example.mylittlechef.telemetry

import com.example.mylittlechef.domain.CookingRun
import com.example.mylittlechef.domain.CookingUsage
import com.example.mylittlechef.domain.DishRecipe
import com.example.mylittlechef.domain.RecipeStep
import com.example.mylittlechef.domain.Telemetry
import com.example.mylittlechef.domain.Usage
import com.example.mylittlechef.domain.UsageEvent
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Cooking-mode events: start once per run, exit with steps reached, completion with its duration. */
class CookingUsageTest {
    private class Recorder : Telemetry {
        val events = mutableListOf<Usage>()
        override fun track(usage: Usage) { events += usage }
    }

    private var now = 1_000L
    private val telemetry = Recorder()
    private val cooking = CookingUsage(telemetry) { now }

    private fun run(id: String, revised: Boolean, steps: Int) = CookingRun(id, "두부조림", revised, RECIPE.copy(steps = List(steps) { RecipeStep(it + 1, "step $it") }))

    @Test fun startIsRecordedOncePerRunEvenWhenTheScreenRecomposes() {
        val first = run("r1", revised = false, steps = 4)
        cooking.cookStart("tofu-braise", first)
        cooking.cookStart("tofu-braise", first) // rotation: the effect runs again for the same run
        val start = telemetry.events.single()
        assertEquals(UsageEvent.COOK_START, start.event)
        assertEquals("original", start.recipe)
        assertEquals(4, start.steps)
        assertEquals("tofu-braise", start.dishId)
    }

    @Test fun exitCarriesTheStepReachedAndTheTotal() {
        val r = run("r2", revised = true, steps = 5)
        cooking.cookStart("tofu-braise", r)
        cooking.cookExit("tofu-braise", r, reached = 2)
        val exit = telemetry.events.last()
        assertEquals(UsageEvent.COOK_EXIT, exit.event)
        assertEquals(2, exit.count)
        assertEquals(5, exit.steps)
        assertEquals("revised", exit.recipe)
        cooking.cookExit("tofu-braise", r, reached = 9)
        assertEquals(5, telemetry.events.last().count) // never more than the steps
    }

    @Test fun completionCarriesTheTimeSinceStart() {
        val r = run("r3", revised = false, steps = 3)
        cooking.cookStart("tofu-braise", r)
        now += 95_000
        cooking.cookComplete("tofu-braise", r)
        val done = telemetry.events.last()
        assertEquals(UsageEvent.COOK_COMPLETE, done.event)
        assertEquals(95_000L, done.durationMs)
        assertEquals("original", done.recipe)
        // A completion whose start is unknown (process restarted mid-cooking) has no duration.
        cooking.cookComplete("tofu-braise", run("r4", revised = false, steps = 3))
        assertNull(telemetry.events.last().durationMs)
    }

    @Test fun aNewRunAfterAnExitStartsAgain() {
        val a = run("a", revised = false, steps = 2)
        cooking.cookStart("d", a); cooking.cookExit("d", a, 1)
        val b = run("b", revised = false, steps = 2)
        cooking.cookStart("d", b)
        assertEquals(listOf(UsageEvent.COOK_START, UsageEvent.COOK_EXIT, UsageEvent.COOK_START), telemetry.events.map { it.event })
    }

    private companion object {
        val RECIPE = DishRecipe(
            dishId = "tofu-braise", name = "두부조림", videoTitle = null, videoChannel = null, servings = 2,
            ingredients = emptyList(), steps = emptyList(), tips = emptyList(), uncertain = emptyList(), captionGaps = false
        )
    }
}
