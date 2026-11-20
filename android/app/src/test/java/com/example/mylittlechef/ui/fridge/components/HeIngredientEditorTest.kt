// AI-assisted HE regressions, 2026-11-09; manual review pending.
package com.example.mylittlechef.ui.fridge.components

import com.example.mylittlechef.model.Ingredient
import org.junit.Assert.*
import org.junit.Test

class HeIngredientEditorTest {
    @Test fun undoMergesDeletedRowWithoutRewindingAnotherEditOrNewRow() {
        val editor = IngredientEditorState(listOf("두부", "김치", "계란").map(::Ingredient))
        editor.remove(0)
        editor.rename(0, "배추김치")
        editor.startAdd()
        editor.rename(editor.editingIndex!!, "대파")
        editor.undoRemove()
        assertEquals(listOf("두부", "배추김치", "계란", "대파"), editor.ingredients.map { it.name })
        assertEquals(3, editor.editingIndex)
        assertNull(editor.removedName)
        editor.remove(0)
        editor.replaceAll(listOf(Ingredient("마늘")))
        editor.undoRemove()
        assertEquals(listOf("마늘"), editor.ingredients.map { it.name })
    }

    @Test fun switchingFromEmptyEditorKeepsTargetIndexValid() {
        val editor = IngredientEditorState(listOf("", "김치").map(::Ingredient))
        editor.toggleEdit(0)
        editor.toggleEdit(1)
        assertEquals(0, editor.editingIndex)
        editor.rename(0, "배추김치")
        editor.finishEdit()
        assertEquals(listOf("배추김치"), editor.ingredients.map { it.name })
    }
    @Test fun initialRowsAreEditableAndDeletingEarlierRowKeepsEditingTheSameIngredient() {
        val editor = IngredientEditorState(listOf("두부", "김치", "계란").map(::Ingredient))
        assertEquals(3, editor.ingredients.size)
        editor.toggleEdit(2)
        editor.remove(0)
        assertEquals(1, editor.editingIndex)
        editor.rename(1, "달걀")
        assertEquals(listOf("김치", "달걀"), editor.ingredients.map { it.name })
    }
}
