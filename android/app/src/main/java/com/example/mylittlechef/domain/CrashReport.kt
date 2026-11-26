// AI-generated with Claude Code (Opus 5.5), 2026-11-26; human review pending.
package com.example.mylittlechef.domain

/**
 * What the app keeps of an uncaught exception until the next launch (research/decisions/adr-007-telemetry.md):
 * class names, the first frame of our own code and the phone. It never keeps `exception.message` or
 * `exception.stacktrace`: a message may hold ingredient names, URLs or server replies, a trace the same in its
 * causes. Values are cleaned to the server's patterns, so a crash event can never make the whole usage batch
 * fail with a 422.
 *
 * On the wire (OpenTelemetry names): [type] is `exception.type`, the thrown class; [causeType] is
 * `exception.cause.type` (ours), the innermost cause's class when it differs; [function] and [line] are
 * `code.function.name` and `code.line.number`; [device] is `device.model.identifier`; [apiLevel] is
 * `android.os.api_level` (OpenTelemetry's Android attribute, sent as an integer).
 */
data class CrashRecord(
    val type: String,
    val causeType: String?,
    val function: String?,
    val line: Int?,
    val device: String,
    val apiLevel: Int,
    val t: Long,
    /** Crashes since the last report; a crash loop before the next send keeps only the newest. */
    val count: Int = 1
) {
    fun toUsage() = Usage(
        UsageEvent.CRASH, exceptionType = type, exceptionCauseType = causeType, codeFunction = function,
        codeLine = line, deviceModel = device, apiLevel = apiLevel, count = count, t = t
    )

    /** One `key=value` line per field; cleaned names cannot hold a newline or `=`. */
    fun encode(): String = listOfNotNull(
        "type=$type", causeType?.let { "cause=$it" }, function?.let { "function=$it" }, line?.let { "line=$it" },
        "device=$device", "api=$apiLevel", "t=$t", "count=$count"
    ).joinToString("\n")

    companion object {
        const val APP_PACKAGE = "com.example.mylittlechef"
        const val NATIVE = "native"

        fun of(failure: Throwable, device: String, apiLevel: Int, t: Long, appPackage: String = APP_PACKAGE): CrashRecord {
            val root = rootCause(failure)
            val frame = firstFrame(root, appPackage) ?: firstFrame(failure, appPackage)
                ?: root.stackTrace.firstOrNull() ?: failure.stackTrace.firstOrNull()
            return CrashRecord(
                type = cleanClass(failure.javaClass.name),
                causeType = if (root !== failure) cleanClass(root.javaClass.name) else null,
                function = frame?.let { cleanFunction("${it.className}.${it.methodName}") },
                line = frame?.lineNumber?.takeIf { it >= 0 }?.coerceAtMost(MAX_LINE),
                device = cleanDevice(device),
                apiLevel = cleanApiLevel(apiLevel),
                t = t
            )
        }

        /** Null for a damaged or empty file: a lost crash is better than a crash on start. */
        fun decode(text: String): CrashRecord? {
            val fields = text.lines().mapNotNull { line ->
                val i = line.indexOf('=')
                if (i > 0) line.substring(0, i) to line.substring(i + 1) else null
            }.toMap()
            return CrashRecord(
                type = fields["type"]?.let(::cleanClass) ?: return null,
                causeType = fields["cause"]?.let(::cleanClass),
                function = fields["function"]?.let(::cleanFunction),
                line = fields["line"]?.toIntOrNull()?.takeIf { it >= 0 }?.coerceAtMost(MAX_LINE),
                device = fields["device"]?.let(::cleanDevice) ?: return null,
                apiLevel = fields["api"]?.toIntOrNull()?.let(::cleanApiLevel) ?: return null,
                t = fields["t"]?.toLongOrNull()?.takeIf { it >= 0 } ?: return null,
                count = fields["count"]?.toIntOrNull()?.coerceIn(1, 10_000) ?: 1
            )
        }

        private const val MAX_LINE = 999_999

        private fun rootCause(failure: Throwable): Throwable {
            var current = failure
            val seen = mutableSetOf<Throwable>()
            while (true) {
                val next = current.cause ?: return current
                if (!seen.add(current) || next === current) return current
                current = next
            }
        }

        private fun firstFrame(failure: Throwable, appPackage: String) =
            failure.stackTrace.firstOrNull { it.className.startsWith("$appPackage.") }

        /** Server pattern for `code.function.name`: `^[A-Za-z0-9_$.<>]{1,200}$`. */
        fun cleanFunction(value: String): String? =
            value.replace(Regex("[^A-Za-z0-9_$.<>]"), "_").take(200).ifEmpty { null }

        /** Server pattern for `exception.type`: `^[A-Za-z_$][A-Za-z0-9_$.]{0,199}$`. */
        fun cleanClass(value: String): String {
            val cleaned = value.replace(Regex("[^A-Za-z0-9_$.]"), "_").take(200)
            return if (cleaned.isEmpty() || !(cleaned[0].isLetter() || cleaned[0] == '_' || cleaned[0] == '$'))
                "_${cleaned.take(199)}" else cleaned
        }

        /** Server pattern for `device.model.identifier`: `^[A-Za-z0-9 ._()+-]{1,64}$` (the maker's model name). */
        fun cleanDevice(value: String): String =
            value.replace(Regex("[^A-Za-z0-9 ._()+-]"), "_").take(64).ifBlank { "unknown" }

        fun cleanApiLevel(value: Int): Int = value.coerceIn(1, 99)
    }
}
