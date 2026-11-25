// UAT stage 4 assisted by Codex, 2026-11-24; human review pending.
package com.example.mylittlechef.domain

data class GuideZone(val top:Float,val height:Float)
/** Select the larger safe area outside the actual target; the card scrolls inside it. */
fun guideCalloutZone(safeTop:Float,safeBottom:Float,targetTop:Float?,targetBottom:Float?,gap:Float):GuideZone {
    val top=safeTop.coerceAtLeast(0f)
    val bottom=safeBottom.coerceAtLeast(top)
    if(targetTop==null || targetBottom==null || targetBottom<=top || targetTop>=bottom)
        return GuideZone(top,bottom-top)
    val above=(targetTop-gap-top).coerceAtLeast(0f)
    val belowTop=(targetBottom+gap).coerceIn(top,bottom)
    val below=bottom-belowTop
    return if(above>=below) GuideZone(top,above.coerceAtMost(bottom-top)) else GuideZone(belowTop,below)
}
