// UAT stage 1 assisted by Codex, 2026-11-24; human review pending.
package com.example.mylittlechef.ui.fridge
import androidx.compose.runtime.*
import androidx.compose.runtime.saveable.*
@Stable class FridgeTransientState {
 var selecting by mutableStateOf(false)
 var selectedNames by mutableStateOf(listOf<String>())
 var confirming by mutableStateOf(false)
 var showSuggestions by mutableStateOf(false)
 var ingredientRecipes by mutableStateOf<String?>(null)
 fun reset() { selecting=false; selectedNames=emptyList(); confirming=false; showSuggestions=false; ingredientRecipes=null }
 companion object { val Saver=listSaver<FridgeTransientState,Any>(
 save={listOf("v2",it.selecting,it.confirming,it.showSuggestions,it.ingredientRecipes.orEmpty())+it.selectedNames},
 restore={v->FridgeTransientState().apply {
  if(v.firstOrNull()=="v2") {
   selecting=v[1] as Boolean;confirming=v[2] as Boolean;showSuggestions=v[3] as Boolean
   ingredientRecipes=(v[4] as String).ifBlank {null};selectedNames=v.drop(5).map {it as String}
  } else {selecting=v[0] as Boolean;confirming=v[1] as Boolean;showSuggestions=v[2] as Boolean;selectedNames=v.drop(3).map {it as String}}
 }}) }
}
@Composable fun rememberFridgeTransientState()=rememberSaveable(saver=FridgeTransientState.Saver) {FridgeTransientState()}
