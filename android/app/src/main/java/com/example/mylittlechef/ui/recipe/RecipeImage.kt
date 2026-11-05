// Teammate recipe-image integration adapted with Codex, 2026-11-03; human review pending.
package com.example.mylittlechef.ui.recipe

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import coil3.compose.AsyncImage
import com.example.mylittlechef.model.Recipe
import com.example.mylittlechef.ui.theme.DeepGreen

/** Shared list/detail rendering. Missing, loading or failed remote images retain a fallback. */
@Composable
fun RecipeImage(recipe: Recipe, modifier: Modifier = Modifier) {
    Box(modifier.background(DeepGreen)) {
        recipe.imageRes?.let { drawable ->
            Image(painterResource(drawable),contentDescription=if(recipe.imageUrl==null) recipe.name else null,
                contentScale=ContentScale.Crop,modifier=Modifier.fillMaxSize())
        }
        recipe.imageUrl?.let { url ->
            AsyncImage(model=url,contentDescription=recipe.name,contentScale=ContentScale.Crop,
                modifier=Modifier.fillMaxSize())
        }
    }
}
