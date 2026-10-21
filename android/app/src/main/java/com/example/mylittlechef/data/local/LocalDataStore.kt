// AI-assisted with Codex (GPT-6.1 Sol), 2026-10-14; human review pending.
package com.example.mylittlechef.data.local

import android.content.Context
import androidx.datastore.preferences.preferencesDataStore

val Context.localDataStore by preferencesDataStore(name = "my_little_chef")
