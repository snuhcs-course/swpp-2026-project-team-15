// AI-generated with Claude Code (Opus 5.5), 2026-10-11; reviewed by Jaehyuk Choi.
package com.example.mylittlechef.data.remote

import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import retrofit2.http.Body
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import java.util.concurrent.TimeUnit

interface MyLittleChefApi {
    @Multipart
    @POST("analyze")
    suspend fun analyze(@Part image: MultipartBody.Part): AnalyzeResponse

    @POST("recipes/recommend")
    suspend fun recommend(@Body request: RecommendRequest): RecommendResponse
}

object ApiClient {
    // The phone reaches the laptop's server through `adb reverse tcp:8000 tcp:8000`.
    private const val BASE_URL = "http://127.0.0.1:8000/"

    val api: MyLittleChefApi by lazy {
        val http = OkHttpClient.Builder()
            // Image recognition can exceed OkHttp's 10 s default read timeout.
            .readTimeout(60, TimeUnit.SECONDS)
            .build()
        Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(http)
            .addConverterFactory(GsonConverterFactory.create())
            .build()
            .create(MyLittleChefApi::class.java)
    }
}
