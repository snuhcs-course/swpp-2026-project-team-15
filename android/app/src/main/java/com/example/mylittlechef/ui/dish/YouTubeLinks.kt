// AI-assisted with Claude Code (Sonnet 5.5), 2026-11-16; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.ui.dish

import android.content.ActivityNotFoundException
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.widget.Toast

/** Opens a web link; the YouTube app takes it when installed, otherwise the browser does. */
fun openLink(context: Context, url: String) {
    val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    try {
        context.startActivity(intent)
    } catch (_: ActivityNotFoundException) {
        Toast.makeText(context, "링크를 열 수 있는 앱이 없어요.", Toast.LENGTH_SHORT).show()
    }
}
