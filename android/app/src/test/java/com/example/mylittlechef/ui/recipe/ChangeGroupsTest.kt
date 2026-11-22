// AI-generated with Claude Code (Opus 5.5), 2026-11-19; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.ui.recipe

import com.example.mylittlechef.domain.ChangeKind
import com.example.mylittlechef.domain.RecipeChange
import com.example.mylittlechef.domain.changeKindOf
import org.junit.Assert.assertEquals
import org.junit.Test

class ChangeGroupsTest {
    private fun change(reason: String, kind: String?) =
        RecipeChange(reason, emptyList(), emptyList(), changeKindOf(kind))

    // The user's choice (2026-11-19): the revised recipe shows what was left out and what was used
    // instead, as the team's earlier revision labelled changes.
    @Test fun groupsByKindAndKeepsOrderAndDropsEmptyGroups() {
        val groups = changeGroups(
            listOf(change("대파 없음", "omission"), change("양 줄임", "quantity"), change("계란 없음", "omission"))
        )
        assertEquals(listOf("뺀 재료", "그 밖에 바뀐 점"), groups.map { it.first })
        assertEquals(listOf("대파 없음", "계란 없음"), groups[0].second.map { it.reason })
    }

    @Test fun anOlderServerWithoutKindsShowsEverythingUnderTheRest() {
        assertEquals(ChangeKind.OTHER, changeKindOf(null))
        assertEquals(listOf("그 밖에 바뀐 점"), changeGroups(listOf(change("x", null))).map { it.first })
        assertEquals(ChangeKind.SUBSTITUTION, changeKindOf("substitution"))
    }
}
