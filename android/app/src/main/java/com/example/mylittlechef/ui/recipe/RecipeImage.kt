// Photo fallback and image crossfade assisted by Codex, 2026-11-19; human review pending.
// Teammate recipe-image integration adapted with Codex, 2026-11-03; human review pending.
// Restored on the YouTube-based dishes with Claude Code (Opus 5.5), 2026-11-20: the photo is the
// still image of the dish's recipe video.

package com.example.mylittlechef.ui.recipe
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import coil3.compose.AsyncImage
import coil3.request.ImageRequest
import coil3.request.crossfade
import com.example.mylittlechef.R

@Composable fun RecipeImage(name:String,imageUrl:String?,modifier:Modifier=Modifier,playMark:Boolean=false) {
    val context=LocalContext.current
    var loaded by remember(imageUrl){mutableStateOf(false)}
    Box(modifier.background(MaterialTheme.colorScheme.surfaceVariant),contentAlignment=Alignment.Center) {
        if(!loaded) Column(horizontalAlignment=Alignment.CenterHorizontally,verticalArrangement=Arrangement.spacedBy(8.dp)) {
            Icon(painterResource(R.drawable.ic_recipe),contentDescription=null,modifier=Modifier.size(32.dp),tint=MaterialTheme.colorScheme.onSurfaceVariant)
            Text("요리 사진 준비 중",style=MaterialTheme.typography.bodySmall,color=MaterialTheme.colorScheme.onSurfaceVariant)
        }
        imageUrl?.let{url->AsyncImage(model=remember(context,url){ImageRequest.Builder(context).data(url).crossfade(180).build()},
            contentDescription=name,contentScale=ContentScale.Crop,modifier=Modifier.fillMaxSize(),onSuccess={loaded=true},onError={loaded=false})}
        // The card opens the dish's video; the mark says so.
        if(playMark&&loaded) Box(Modifier.align(Alignment.BottomStart).padding(10.dp).size(32.dp).clip(CircleShape).background(Color(0x99000000)),contentAlignment=Alignment.Center) {
            Icon(painterResource(R.drawable.ic_play),contentDescription=null,tint=Color.White,modifier=Modifier.size(16.dp))
        }
    }
}
