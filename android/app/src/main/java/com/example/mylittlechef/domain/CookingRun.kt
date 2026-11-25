// UAT stage 4 assisted by Codex, 2026-11-24; human review pending.
package com.example.mylittlechef.domain
import java.util.UUID

/** Activity-scoped snapshot only; never persisted in the user's repositories. */
data class CookingRun(val id:String,val name:String,val revised:Boolean,val recipe:DishRecipe)
fun startCookingRun(source:DishRecipe,revision:Revision.Revised?=null,name:String=source.name):CookingRun {
    val shown=if(revision==null) source else source.copy(
        servings=revision.servings ?: source.servings,
        ingredients=revision.ingredients.map {RecipeIngredient(it.name,it.amount,Availability.OWNED)},
        steps=revision.steps,tips=revision.tips)
    return CookingRun(UUID.randomUUID().toString(),name,revision!=null,shown)
}
