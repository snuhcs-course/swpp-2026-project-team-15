// AI-generated with Claude Code (Opus 5.5), 2026-11-26; human review pending.
package com.example.mylittlechef.domain

/** What the cooking mode reports; the recipe screen calls it, DishViewModel implements it. */
interface CookingTracker {
    /** The cooking cards opened; safe to call again for the same run (a rotation recomposes the screen). */
    fun cookStart(dishId: String, run: CookingRun)

    /** "조리 종료" confirmed on step [reached] (1-based) of the run. */
    fun cookExit(dishId: String, run: CookingRun, reached: Int)

    /** The last step's "요리 완료". */
    fun cookComplete(dishId: String, run: CookingRun)
}

/**
 * Usage events of the cooking mode (research/decisions/adr-007-telemetry.md): the dish id, which recipe
 * (original or revised), steps reached and total, time from start to completion. Start times live here, in the
 * ViewModel, so a rotation keeps them; a run is identified by [CookingRun.id].
 */
class CookingUsage(private val telemetry: Telemetry, private val clock: () -> Long = System::currentTimeMillis) :
    CookingTracker {
    private val started = mutableMapOf<String, Long>()

    override fun cookStart(dishId: String, run: CookingRun) {
        if (run.id in started) return
        started[run.id] = clock()
        telemetry.track(Usage(UsageEvent.COOK_START, dishId = dishId, recipe = recipeOf(run), steps = stepsOf(run)))
    }

    override fun cookExit(dishId: String, run: CookingRun, reached: Int) {
        started.remove(run.id)
        val steps = stepsOf(run)
        telemetry.track(
            Usage(UsageEvent.COOK_EXIT, dishId = dishId, recipe = recipeOf(run), count = reached.coerceIn(0, steps), steps = steps)
        )
    }

    override fun cookComplete(dishId: String, run: CookingRun) {
        val start = started.remove(run.id)
        telemetry.track(
            Usage(
                UsageEvent.COOK_COMPLETE, dishId = dishId, recipe = recipeOf(run), steps = stepsOf(run),
                durationMs = start?.let { (clock() - it).coerceAtLeast(0) }
            )
        )
    }

    private fun recipeOf(run: CookingRun) = if (run.revised) "revised" else "original"
    private fun stepsOf(run: CookingRun) = run.recipe.steps.size.coerceAtMost(MAX_STEPS)

    private companion object {
        const val MAX_STEPS = 500
    }
}
