// UAT stage 3 assisted by Codex, 2026-11-24; human review pending.
package com.example.mylittlechef.domain

/** Amount already contains the server's quantity/unit text. Never infer or convert it. */
fun copyRecipeIngredients(name:String,revised:Boolean,rows:List<Pair<String,String?>>):String = buildString {
    append(name);append(if(revised) " — AI 수정본" else " — 원본 레시피");append("\n재료\n")
    append(rows.joinToString("\n") { (ingredient,amount) ->
        "- "+ingredient+(amount?.takeIf {it.isNotBlank()}?.let {" $it"} ?: "")
    })
}

/** Uses the same sequential numbering as RecipeSteps on screen. */
fun copyRecipeSteps(name:String,revised:Boolean,steps:List<String>):String = buildString {
    append(name);append(if(revised) " — AI 수정본" else " — 원본 레시피");append("\n조리 방법\n")
    append(steps.mapIndexed {i,text->"${i+1}. $text"}.joinToString("\n"))
}
