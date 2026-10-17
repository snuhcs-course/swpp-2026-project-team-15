package com.example.mylittlechef.data.local

import android.content.Context
import androidx.datastore.preferences.preferencesDataStore

val Context.localDataStore by preferencesDataStore(name = "my_little_chef")
