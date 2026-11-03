// AI-assisted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.domain

enum class ThemeMode(val label: String) {
    SYSTEM("시스템 설정"), LIGHT("라이트 모드"), DARK("다크 모드");

    fun isDark(systemDark: Boolean): Boolean = when (this) {
        SYSTEM -> systemDark
        LIGHT -> false
        DARK -> true
    }
}
