// AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.ui.profile

import org.junit.Assert.assertTrue
import org.junit.Test

class DataResetCopyTest {
    // Found on the phone (2026-11-19): the row left out the screen mode that the reset also clears.
    @Test
    fun rowAndDialogNameEverythingTheResetErases() {
        for (text in listOf(DataResetCopy.SUMMARY, DataResetCopy.CONFIRM)) {
            for (part in listOf("냉장고", "프로필", "즐겨찾기", "화면 모드")) {
                assertTrue("$part missing in: $text", part in text)
            }
        }
    }
}
