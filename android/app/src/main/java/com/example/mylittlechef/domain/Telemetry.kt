// AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
// Modified with Claude Code (Opus 5.5), 2026-11-26: crash and ANR events (see CrashReport.kt, ProcessExits.kt).
package com.example.mylittlechef.domain

import retrofit2.HttpException

/**
 * Usage data for the beta week (research/decisions/adr-007-telemetry.md). The names and fields match the
 * server's closed schema: counts, durations, dish ids and statuses only, never ingredient names, photos or text.
 */
enum class UsageEvent(val wire: String) {
    SESSION_START("session_start"),
    SESSION_END("session_end"),
    SCREEN_VIEW("screen_view"),
    FRIDGE_ADD("fridge_add"),
    RECOGNITION("recognition"),
    DISH_LIST("dish_list"),
    DISH_OPEN("dish_open"),
    RECIPE_VIEW("recipe_view"),
    REVISE("revise"),
    PLAYER_ERROR("player_error"),
    CRASH("crash"),
    ANR("anr")
}

data class Usage(
    val event: UsageEvent,
    val dishId: String? = null,
    val count: Int? = null,
    val durationMs: Long? = null,
    /** ok, empty, error, revised, refused or failed. */
    val status: String? = null,
    /** photo, manual, suggestion or pantry. */
    val source: String? = null,
    val screen: String? = null,
    /** HTTP status of a failed request; null when the server was not reached. */
    val code: Int? = null,
    /** Crash only: exception and root cause class names, first app frame, phone model, API level. */
    val error: String? = null,
    val cause: String? = null,
    val where: String? = null,
    val device: String? = null,
    val sdk: Int? = null,
    val t: Long = System.currentTimeMillis()
)

/** The role the ViewModels depend on; the app creates one [Telemetry] and hands it in. */
interface Telemetry {
    fun track(usage: Usage)

    /** Sends what is buffered; the app calls it when it goes to the background. */
    fun flush() {}
}

/** For tests and previews, and the default where nothing is injected. */
object NoTelemetry : Telemetry {
    override fun track(usage: Usage) = Unit
}

fun failureCode(failure: Exception): Int? = (failure as? HttpException)?.code()
