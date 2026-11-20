// AI-generated with Claude Code (Opus 5.5), 2026-11-20; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.viewmodel

import java.io.FileNotFoundException
import java.io.IOException
import org.junit.Assert.assertEquals
import org.junit.Test

class PhotoFailureMessageTest {
    // Emulator E2E (2026-11-20): an unreadable picked photo was reported as a network problem.
    @Test fun unreadablePhotoIsNotReportedAsANetworkProblem() {
        assertEquals("사진을 불러올 수 없어요. 다시 고르거나 직접 입력해 주세요.", photoAnalysisFailure(FileNotFoundException("x")))
        assertEquals("사진을 불러올 수 없어요. 다시 고르거나 직접 입력해 주세요.", photoAnalysisFailure(SecurityException("x")))
        assertEquals("연결을 확인하고 다시 시도해 주세요. 직접 입력도 가능해요.", photoAnalysisFailure(IOException("x")))
    }
}
