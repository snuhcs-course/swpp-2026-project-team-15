// AI-generated with Claude Code (Opus 5.5), 2026-11-26; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.domain

/**
 * What the app keeps of an uncaught exception until the next launch (research/decisions/adr-007-telemetry.md):
 * class names, the first frame of our own code and the phone, never the exception message, which may hold
 * ingredient names, URLs or other user data. Values are cleaned to the server's patterns, so a crash event
 * can never make the whole usage batch fail with a 422.
 */
data class CrashRecord(
    val error: String,
    val cause: String?,
    val where: String?,
    val device: String,
    val sdk: Int,
    val t: Long,
    /** Crashes since the last report; a crash loop before the next send keeps only the newest. */
    val count: Int = 1
) {
    fun toUsage() = Usage(
        UsageEvent.CRASH, error = error, cause = cause, where = where, device = device, sdk = sdk,
        count = count, t = t
    )

    /** One `key=value` line per field; names cannot hold a newline or `=` after cleaning. */
    fun encode(): String = listOfNotNull(
        "error=$error", cause?.let { "cause=$it" }, where?.let { "where=$it" },
        "device=$device", "sdk=$sdk", "t=$t", "count=$count"
    ).joinToString("\n")

    companion object {
        const val APP_PACKAGE = "com.example.mylittlechef"

        fun of(failure: Throwable, device: String, sdk: Int, t: Long, appPackage: String = APP_PACKAGE): CrashRecord {
            val root = rootCause(failure)
            val frame = firstFrame(root, appPackage) ?: firstFrame(failure, appPackage)
                ?: root.stackTrace.firstOrNull() ?: failure.stackTrace.firstOrNull()
            return CrashRecord(
                error = className(failure.javaClass.name),
                cause = if (root !== failure) className(root.javaClass.name) else null,
                where = frame?.let(::place),
                device = cleanDevice(device),
                sdk = sdk.coerceIn(1, 99),
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
                error = fields["error"]?.let(::className) ?: return null,
                cause = fields["cause"]?.let(::className),
                where = fields["where"]?.let(::cleanPlace),
                device = fields["device"]?.let(::cleanDevice) ?: return null,
                sdk = fields["sdk"]?.toIntOrNull()?.coerceIn(1, 99) ?: return null,
                t = fields["t"]?.toLongOrNull()?.takeIf { it >= 0 } ?: return null,
                count = fields["count"]?.toIntOrNull()?.coerceIn(1, 10_000) ?: 1
            )
        }

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

        private fun place(frame: StackTraceElement): String? {
            val line = if (frame.lineNumber >= 0) ":${frame.lineNumber.coerceAtMost(999_999)}" else ""
            return cleanPlace("${frame.className}.${frame.methodName}")?.let { it + line }
        }

        /** Server pattern: `^[A-Za-z0-9_$.<>]{1,200}(:[0-9]{1,6})?$`. */
        private fun cleanPlace(value: String): String? {
            val line = Regex(":[0-9]{1,6}$").find(value)?.value.orEmpty()
            val name = value.removeSuffix(line).replace(Regex("[^A-Za-z0-9_$.<>]"), "_").take(200)
            return if (name.isEmpty()) null else name + line
        }

        /** Server pattern: `^[A-Za-z_$][A-Za-z0-9_$.]{0,199}$`. */
        private fun className(value: String): String {
            val cleaned = value.replace(Regex("[^A-Za-z0-9_$.]"), "_").take(200)
            return if (cleaned.isEmpty() || !(cleaned[0].isLetter() || cleaned[0] == '_' || cleaned[0] == '$'))
                "_${cleaned.take(199)}" else cleaned
        }

        /** Server pattern: `^[A-Za-z0-9 ._()+-]{1,64}$`; the model name set by the maker, not the owner. */
        fun cleanDevice(value: String): String =
            value.replace(Regex("[^A-Za-z0-9 ._()+-]"), "_").take(64).ifBlank { "unknown" }
    }
}
