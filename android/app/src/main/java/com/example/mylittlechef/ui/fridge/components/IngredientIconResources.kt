// AI-assisted with Codex, 2026-11-02; human review pending.
package com.example.mylittlechef.ui.fridge.components

import androidx.annotation.DrawableRes
import com.example.mylittlechef.R

@DrawableRes
fun ingredientIconResource(key: String): Int = when (key) {
    "leafy" -> R.drawable.ic_ingredient_leafy
    "root" -> R.drawable.ic_ingredient_root
    "fruit_vegetable" -> R.drawable.ic_ingredient_fruit_vegetable
    "onion" -> R.drawable.ic_ingredient_onion
    "scallion" -> R.drawable.ic_ingredient_scallion
    "garlic" -> R.drawable.ic_ingredient_garlic
    "sprouts" -> R.drawable.ic_ingredient_sprouts
    "mushroom" -> R.drawable.ic_ingredient_mushroom
    "fruit" -> R.drawable.ic_ingredient_fruit
    "meat" -> R.drawable.ic_ingredient_meat
    "chicken" -> R.drawable.ic_ingredient_chicken
    "fish" -> R.drawable.ic_ingredient_fish
    "shrimp" -> R.drawable.ic_ingredient_shrimp
    "squid" -> R.drawable.ic_ingredient_squid
    "seaweed" -> R.drawable.ic_ingredient_seaweed
    "egg" -> R.drawable.ic_ingredient_egg
    "milk" -> R.drawable.ic_ingredient_milk
    "cheese" -> R.drawable.ic_ingredient_cheese
    "tofu" -> R.drawable.ic_ingredient_tofu
    "beans" -> R.drawable.ic_ingredient_beans
    "rice" -> R.drawable.ic_ingredient_rice
    "noodles" -> R.drawable.ic_ingredient_noodles
    "bread" -> R.drawable.ic_ingredient_bread
    "rice_cake" -> R.drawable.ic_ingredient_rice_cake
    "kimchi" -> R.drawable.ic_ingredient_kimchi
    "seasoning" -> R.drawable.ic_ingredient_seasoning
    "stock" -> R.drawable.ic_ingredient_stock
    "generic" -> R.drawable.ic_ingredient_generic
    else -> R.drawable.ic_ingredient_generic
}
