// Photo fallback and image crossfade assisted by Codex, 2026-11-19; human review pending.
// Teammate recipe-image integration adapted with Codex, 2026-11-03; human review pending.

package com.example.mylittlechef.ui.recipe
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import coil3.request.ImageRequest
import coil3.request.crossfade
import com.example.mylittlechef.R
import com.example.mylittlechef.model.Recipe

@Composable fun RecipeImage(recipe:Recipe,modifier:Modifier=Modifier) {
    val context=LocalContext.current
    var loaded by remember(recipe.imageUrl){mutableStateOf(false)}
    Box(modifier.background(MaterialTheme.colorScheme.surfaceVariant),contentAlignment=Alignment.Center) {
        if(!loaded) {
            if(recipe.imageRes!=null)Image(painterResource(recipe.imageRes),contentDescription=null,contentScale=ContentScale.Crop,modifier=Modifier.fillMaxSize())
            else Column(horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.spacedBy(8.dp)) {
                Icon(painterResource(R.drawable.ic_recipe),contentDescription=null,modifier=Modifier.size(32.dp),tint=MaterialTheme.colorScheme.onSurfaceVariant)
                Text("요리 사진 준비 중",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        recipe.imageUrl?.let{url->AsyncImage(model=remember(context,url){ImageRequest.Builder(context).data(url).crossfade(180).build()},
            contentDescription=recipe.name,contentScale=ContentScale.Crop,modifier=Modifier.fillMaxSize(),onSuccess={loaded=true},onError={loaded=false})}
    }
}
